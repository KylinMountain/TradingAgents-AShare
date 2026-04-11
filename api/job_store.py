"""JobStore abstraction for managing analysis job state and SSE events.

Provides a Protocol defining the interface and an InMemoryJobStore implementation
that replicates the current module-level _jobs / _job_events behavior in api/main.py.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@runtime_checkable
class JobStore(Protocol):
    """Interface for job state + event storage."""

    def set_job(self, job_id: str, **fields: Any) -> None:
        """Create or update job fields (merge semantics, thread-safe)."""
        ...

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Return job fields as dict, or empty dict if not found."""
        ...

    def delete_job(self, job_id: str) -> None:
        """Remove job state and associated event queue."""
        ...

    def emit_event(self, job_id: str, event: str, data: Dict[str, Any]) -> None:
        """Push SSE event for job (thread-safe, works from both event loop and worker threads)."""
        ...

    def subscribe(self, job_id: str, *, poll_interval: float = 15.0) -> AsyncIterator[Dict[str, Any]]:
        """Async generator yielding events.

        On timeout with no events: yield ping if job still running,
        or terminate if completed/failed.
        Terminal events: job.completed, job.failed.
        """
        ...

    def clear(self) -> None:
        """Reset all state (used on startup)."""
        ...


class InMemoryJobStore:
    """In-process job store using threading.Lock and asyncio.Queue.

    This matches the exact behavior of the module-level _jobs dict,
    _job_events queues, and helper functions in api/main.py.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._job_events: Dict[str, asyncio.Queue[Dict[str, Any]]] = {}

    # ── state management ────────────────────────────────────────────────

    def set_job(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            if job_id not in self._jobs:
                self._jobs[job_id] = {}
            self._jobs[job_id].update(fields)

    def get_job(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            return dict(self._jobs.get(job_id, {}))

    def delete_job(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)
            self._job_events.pop(job_id, None)

    # ── event queue ─────────────────────────────────────────────────────

    def _ensure_queue(self, job_id: str) -> asyncio.Queue[Dict[str, Any]]:
        with self._lock:
            q = self._job_events.get(job_id)
            if q is None:
                q = asyncio.Queue()
                self._job_events[job_id] = q
            return q

    def emit_event(self, job_id: str, event: str, data: Dict[str, Any]) -> None:
        """Thread-safe event emitter.

        Uses put_nowait directly when called from the event loop,
        and call_soon_threadsafe when called from a worker thread.
        """
        payload: Dict[str, Any] = {
            "event": event,
            "data": data,
            "timestamp": _utcnow_iso(),
        }
        q = self._ensure_queue(job_id)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            q.put_nowait(payload)
        else:
            try:
                main_loop = asyncio.get_event_loop()
                main_loop.call_soon_threadsafe(q.put_nowait, payload)
            except RuntimeError:
                q.put_nowait(payload)

    async def subscribe(
        self, job_id: str, *, poll_interval: float = 15.0
    ) -> AsyncIterator[Dict[str, Any]]:
        """Async generator yielding events for *job_id*.

        On timeout:
          - If job is still running, yield a ping event.
          - If job is completed or failed, terminate the generator.
        On terminal events (job.completed, job.failed), yield and terminate.
        """
        q = self._ensure_queue(job_id)
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=poll_interval)
                yield event
                if event["event"] in ("job.completed", "job.failed"):
                    break
            except asyncio.TimeoutError:
                with self._lock:
                    status = self._jobs.get(job_id, {}).get("status")
                if status in ("completed", "failed"):
                    break
                yield {
                    "event": "ping",
                    "data": {"timestamp": _utcnow_iso()},
                    "timestamp": _utcnow_iso(),
                }

    # ── lifecycle ───────────────────────────────────────────────────────

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
            self._job_events.clear()


def get_job_store() -> JobStore:
    """Factory that returns a JobStore implementation.

    Returns RedisJobStore when REDIS_URL environment variable is set
    (requires api.job_store_redis module), otherwise InMemoryJobStore.
    """
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            from api.job_store_redis import RedisJobStore
            return RedisJobStore(redis_url)
        except ImportError:
            logger.warning(
                "REDIS_URL is set but api.job_store_redis is not available; "
                "falling back to InMemoryJobStore"
            )
    return InMemoryJobStore()
