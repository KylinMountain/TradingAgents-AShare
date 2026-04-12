from __future__ import annotations

import asyncio

from api.job_store import InMemoryJobStore


def _make_store() -> InMemoryJobStore:
    return InMemoryJobStore()


def test_set_and_get_job():
    store = _make_store()
    store.set_job("j1", status="running", symbol="AAPL")
    job = store.get_job("j1")
    assert job == {"status": "running", "symbol": "AAPL"}


def test_get_missing_job():
    store = _make_store()
    assert store.get_job("nonexistent") == {}


def test_set_job_merges():
    store = _make_store()
    store.set_job("j1", status="running")
    store.set_job("j1", symbol="AAPL")
    job = store.get_job("j1")
    assert job == {"status": "running", "symbol": "AAPL"}
    # Overwrite existing field
    store.set_job("j1", status="completed")
    job = store.get_job("j1")
    assert job == {"status": "completed", "symbol": "AAPL"}


def test_delete_job():
    store = _make_store()
    store.set_job("j1", status="running")
    store.delete_job("j1")
    assert store.get_job("j1") == {}
    # Deleting non-existent job should not raise
    store.delete_job("j1")


def test_emit_and_subscribe():
    async def scenario():
        store = _make_store()
        store.set_job("j1", status="running")

        store.emit_event("j1", "agent.snapshot", {"step": 1})
        store.emit_event("j1", "agent.snapshot", {"step": 2})
        store.emit_event("j1", "job.completed", {"result": "ok"})

        collected = []
        async for event in store.subscribe("j1"):
            collected.append(event)

        assert len(collected) == 3
        assert collected[0]["event"] == "agent.snapshot"
        assert collected[0]["data"] == {"step": 1}
        assert collected[1]["event"] == "agent.snapshot"
        assert collected[1]["data"] == {"step": 2}
        assert collected[2]["event"] == "job.completed"
        assert collected[2]["data"] == {"result": "ok"}
        # Each event should have a timestamp
        for ev in collected:
            assert "timestamp" in ev

    asyncio.run(scenario())


def test_subscribe_timeout_ping():
    async def scenario():
        store = _make_store()
        store.set_job("j1", status="running")

        # Use a very short poll interval so the test completes quickly
        collected = []
        count = 0
        async for event in store.subscribe("j1", poll_interval=0.05):
            collected.append(event)
            count += 1
            if count == 1:
                # After first ping, mark job as completed so next timeout terminates
                store.set_job("j1", status="completed")

        # First event should be a ping (timeout with job still running)
        assert len(collected) == 1
        assert collected[0]["event"] == "ping"
        assert "timestamp" in collected[0]["data"]

    asyncio.run(scenario())


def test_clear():
    store = _make_store()
    store.set_job("j1", status="running")
    store.set_job("j2", status="completed")
    store.clear()
    assert store.get_job("j1") == {}
    assert store.get_job("j2") == {}
