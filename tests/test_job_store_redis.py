"""Tests for RedisJobStore.

Skipped automatically when Redis is not reachable on localhost.
Uses DB 15 to avoid conflicts with production data.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import redis

# ---------------------------------------------------------------------------
# Skip guard: skip the entire module when Redis is unreachable
# ---------------------------------------------------------------------------

_REDIS_TEST_URL = os.environ.get("REDIS_TEST_URL", "redis://localhost:6379/15")

def _redis_available() -> bool:
    try:
        r = redis.Redis.from_url(_REDIS_TEST_URL, decode_responses=True)
        r.ping()
        r.close()
        return True
    except Exception:
        return False

pytestmark = pytest.mark.skipif(
    not _redis_available(),
    reason="Redis not available at " + _REDIS_TEST_URL,
)

from api.job_store_redis import RedisJobStore  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store():
    """Create a RedisJobStore with a unique prefix and flush matching keys after."""
    prefix = f"ta_test:{uuid.uuid4().hex[:8]}:"
    s = RedisJobStore(_REDIS_TEST_URL, prefix=prefix)
    yield s
    # Cleanup: delete all keys with this test prefix
    s.clear()
    s._r.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_set_and_get(store: RedisJobStore):
    store.set_job("j1", status="running", symbol="AAPL")
    job = store.get_job("j1")
    assert job["status"] == "running"
    assert job["symbol"] == "AAPL"


def test_get_missing(store: RedisJobStore):
    assert store.get_job("nonexistent") == {}


def test_merge(store: RedisJobStore):
    store.set_job("j1", status="running")
    store.set_job("j1", symbol="AAPL")
    job = store.get_job("j1")
    assert job["status"] == "running"
    assert job["symbol"] == "AAPL"
    # Overwrite existing field
    store.set_job("j1", status="completed")
    job = store.get_job("j1")
    assert job["status"] == "completed"
    assert job["symbol"] == "AAPL"


def test_none_roundtrip(store: RedisJobStore):
    """None values should round-trip correctly."""
    store.set_job("j1", result=None)
    job = store.get_job("j1")
    assert job["result"] is None


def test_complex_value_roundtrip(store: RedisJobStore):
    """Dict and list values should round-trip via JSON serialization."""
    store.set_job("j1", report={"score": 8, "tags": ["buy", "hold"]}, items=[1, 2, 3])
    job = store.get_job("j1")
    assert job["report"] == {"score": 8, "tags": ["buy", "hold"]}
    assert job["items"] == [1, 2, 3]


def test_delete(store: RedisJobStore):
    store.set_job("j1", status="running")
    store.delete_job("j1")
    assert store.get_job("j1") == {}
    # Deleting a non-existent job should not raise
    store.delete_job("j1")


def test_clear(store: RedisJobStore):
    store.set_job("j1", status="running")
    store.set_job("j2", status="completed")
    store.clear()
    assert store.get_job("j1") == {}
    assert store.get_job("j2") == {}


def test_pubsub(store: RedisJobStore):
    """emit_event + subscribe: events should be delivered in order and
    terminate on a terminal event."""

    async def scenario():
        store.set_job("j1", status="running")

        # Start subscription *before* emitting so the listener is ready
        collected = []
        gen = store.subscribe("j1", poll_interval=5.0)
        # We need the subscriber thread to be up before publishing.
        # Advance the generator to start the thread, then emit events.
        # Use a small delay to let the thread subscribe.
        it = gen.__aiter__()

        # Emit after a short delay to give listener time to subscribe
        async def _emit_later():
            await asyncio.sleep(0.3)
            store.emit_event("j1", "agent.snapshot", {"step": 1})
            store.emit_event("j1", "agent.snapshot", {"step": 2})
            store.emit_event("j1", "job.completed", {"result": "ok"})

        emit_task = asyncio.create_task(_emit_later())

        async for event in gen:
            collected.append(event)

        await emit_task

        assert len(collected) == 3
        assert collected[0]["event"] == "agent.snapshot"
        assert collected[0]["data"] == {"step": 1}
        assert collected[1]["event"] == "agent.snapshot"
        assert collected[1]["data"] == {"step": 2}
        assert collected[2]["event"] == "job.completed"
        assert collected[2]["data"] == {"result": "ok"}
        for ev in collected:
            assert "timestamp" in ev

    asyncio.run(scenario())


def test_subscribe_timeout_ping(store: RedisJobStore):
    """When no events arrive and the job is still running, subscribe yields a
    ping. When the job becomes completed on the next timeout, it terminates."""

    async def scenario():
        store.set_job("j1", status="running")

        collected = []
        count = 0
        async for event in store.subscribe("j1", poll_interval=0.2):
            collected.append(event)
            count += 1
            if count == 1:
                # After first ping, mark job completed so next timeout terminates
                store.set_job("j1", status="completed")

        assert len(collected) == 1
        assert collected[0]["event"] == "ping"
        assert "timestamp" in collected[0]["data"]

    asyncio.run(scenario())
