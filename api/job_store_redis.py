"""Redis-backed JobStore implementation.

Uses Redis Hash for job state and Pub/Sub for real-time SSE event delivery,
enabling multi-worker API deployment where all uvicorn workers share the same
job state and event stream.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict

import redis

logger = logging.getLogger(__name__)

# TTL for job state hashes (seconds). Configurable via env var.
_JOB_STATE_TTL: int = int(os.environ.get("JOB_STATE_TTL", "86400"))

_TERMINAL_EVENTS = frozenset({"job.completed", "job.failed"})


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_value(v: Any) -> str:
    """Serialize a Python value for storage in a Redis Hash field."""
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _deserialize_value(v: str) -> Any:
    """Attempt to deserialize a Redis Hash field value back to Python."""
    if v == "":
        return None
    # Try JSON first (covers dicts, lists, and JSON-encoded scalars)
    try:
        return json.loads(v)
    except (json.JSONDecodeError, ValueError):
        return v


class RedisJobStore:
    """Redis-backed job store using Hash for state and Pub/Sub for events.

    Key schema (all prefixed with *prefix*):
        {prefix}job:{job_id}      -- Redis Hash holding job fields
        {prefix}events:{job_id}   -- Pub/Sub channel for SSE events
    """

    def __init__(self, redis_url: str, prefix: str = "ta:") -> None:
        self._prefix = prefix
        self._r: redis.Redis = redis.Redis.from_url(
            redis_url, decode_responses=True
        )
        # Verify connectivity once at creation
        self._r.ping()
        logger.info("RedisJobStore connected to %s (prefix=%r)", redis_url, prefix)

    # ── key helpers ─────────────────────────────────────────────────────

    def _job_key(self, job_id: str) -> str:
        return f"{self._prefix}job:{job_id}"

    def _channel_key(self, job_id: str) -> str:
        return f"{self._prefix}events:{job_id}"

    # ── state management ────────────────────────────────────────────────

    def set_job(self, job_id: str, **fields: Any) -> None:
        """Create or update job fields (merge semantics).

        Complex values (dict/list) are JSON-serialized; None becomes empty string.
        Each call refreshes the TTL.
        """
        if not fields:
            return
        key = self._job_key(job_id)
        mapping = {k: _serialize_value(v) for k, v in fields.items()}
        pipe = self._r.pipeline()
        pipe.hset(key, mapping=mapping)
        pipe.expire(key, _JOB_STATE_TTL)
        pipe.execute()

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Return job fields as dict, or empty dict if not found."""
        raw = self._r.hgetall(self._job_key(job_id))
        if not raw:
            return {}
        return {k: _deserialize_value(v) for k, v in raw.items()}

    def delete_job(self, job_id: str) -> None:
        """Remove job state hash. Deleting a non-existent key is a no-op."""
        self._r.delete(self._job_key(job_id))

    # ── event pub/sub ───────────────────────────────────────────────────

    def emit_event(self, job_id: str, event: str, data: Dict[str, Any]) -> None:
        """Publish an SSE event payload on the job's Pub/Sub channel."""
        payload: Dict[str, Any] = {
            "event": event,
            "data": data,
            "timestamp": _utcnow_iso(),
        }
        self._r.publish(self._channel_key(job_id), json.dumps(payload, ensure_ascii=False))

    async def subscribe(
        self, job_id: str, *, poll_interval: float = 15.0
    ) -> AsyncIterator[Dict[str, Any]]:
        """Async generator yielding events for *job_id*.

        Internally spins up a background thread running the blocking Redis
        Pub/Sub listener and bridges messages into an asyncio.Queue via
        call_soon_threadsafe.

        On timeout with no events:
          - If job is still running, yield a ping event.
          - If job is completed/failed, terminate the generator.
        On terminal events (job.completed, job.failed), yield and terminate.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        stop_event = threading.Event()

        def _listener() -> None:
            """Blocking listener running in a daemon thread."""
            pubsub = self._r.pubsub()
            try:
                pubsub.subscribe(self._channel_key(job_id))
                while not stop_event.is_set():
                    msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if msg is not None and msg["type"] == "message":
                        try:
                            payload = json.loads(msg["data"])
                        except (json.JSONDecodeError, TypeError):
                            continue
                        loop.call_soon_threadsafe(queue.put_nowait, payload)
            except Exception:
                logger.debug("Redis pubsub listener for %s exiting", job_id, exc_info=True)
            finally:
                try:
                    pubsub.unsubscribe()
                    pubsub.close()
                except Exception:
                    pass

        thread = threading.Thread(target=_listener, daemon=True)
        thread.start()

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=poll_interval)
                    yield event
                    if event["event"] in _TERMINAL_EVENTS:
                        break
                except asyncio.TimeoutError:
                    status = self.get_job(job_id).get("status")
                    if status in ("completed", "failed"):
                        break
                    yield {
                        "event": "ping",
                        "data": {"timestamp": _utcnow_iso()},
                        "timestamp": _utcnow_iso(),
                    }
        finally:
            stop_event.set()
            thread.join(timeout=3.0)

    # ── lifecycle ───────────────────────────────────────────────────────

    def clear(self) -> None:
        """Delete all job state keys matching this store's prefix.

        Uses SCAN to avoid blocking the Redis server with KEYS.
        """
        cursor = 0
        pattern = f"{self._prefix}job:*"
        while True:
            cursor, keys = self._r.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                self._r.delete(*keys)
            if cursor == 0:
                break
