from __future__ import annotations

import asyncio
from unittest.mock import patch

from api.job_store import InMemoryJobStore
from api import main


def _request() -> main.AnalyzeRequest:
    return main.AnalyzeRequest(symbol="600519.SH", trade_date="2026-07-10")


def test_soft_timeout_emits_overtime_then_allows_completion():
    store = InMemoryJobStore()
    events: list[tuple[str, dict]] = []
    store.set_job("job-1", status="running", error="stale error")

    def capture_event(job_id: str, event: str, data: dict) -> None:
        events.append((event, data))
        store.emit_event(job_id, event, data)

    async def scenario() -> None:
        release_inner = asyncio.Event()

        async def fake_inner(job_id, *_args, **_kwargs):
            await release_inner.wait()
            main._set_job(
                job_id,
                status="completed",
                result={"decision": "BUY"},
                error=None,
                overtime=False,
                overtime_at=None,
                finished_at=main._utcnow_iso(),
            )
            main._emit_job_event(job_id, "job.completed", {"job_id": job_id})

        with (
            patch.object(main, "_job_store_instance", store),
            patch.object(main, "_JOB_TIMEOUT", 0.01),
            patch.object(main, "_run_job_inner", side_effect=fake_inner),
            patch.object(main, "_emit_job_event", side_effect=capture_event),
        ):
            wrapper = asyncio.create_task(main._run_job("job-1", _request()))
            await asyncio.sleep(0.02)
            assert not wrapper.done(), "soft deadline must not release the wrapper/scheduler slot"
            assert [event for event, _ in events] == ["job.overtime"]
            assert store.get_job("job-1")["status"] == "running"
            release_inner.set()
            await wrapper

    asyncio.run(scenario())

    job = store.get_job("job-1")
    assert [event for event, _ in events] == ["job.overtime", "job.completed"]
    assert job["status"] == "completed"
    assert job["error"] is None
    assert job["overtime"] is False
    assert events[0][1]["elapsed_seconds"] == 0.01


def test_job_finishing_before_deadline_does_not_emit_overtime():
    store = InMemoryJobStore()
    events: list[str] = []

    async def fake_inner(job_id, *_args, **_kwargs):
        main._set_job(job_id, status="completed", error=None, overtime=False)
        main._emit_job_event(job_id, "job.completed", {"job_id": job_id})

    async def scenario() -> None:
        with (
            patch.object(main, "_job_store_instance", store),
            patch.object(main, "_JOB_TIMEOUT", 1),
            patch.object(main, "_run_job_inner", side_effect=fake_inner),
            patch.object(main, "_emit_job_event", side_effect=lambda _j, event, _d: events.append(event)),
        ):
            await main._run_job("job-fast", _request())

    asyncio.run(scenario())
    assert events == ["job.completed"]


def test_zero_timeout_disables_warning_but_still_waits_for_completion():
    store = InMemoryJobStore()
    events: list[str] = []

    async def fake_inner(job_id, *_args, **_kwargs):
        await asyncio.sleep(0.01)
        main._set_job(job_id, status="completed", error=None, overtime=False)
        main._emit_job_event(job_id, "job.completed", {"job_id": job_id})

    async def scenario() -> None:
        with (
            patch.object(main, "_job_store_instance", store),
            patch.object(main, "_JOB_TIMEOUT", 0),
            patch.object(main, "_run_job_inner", side_effect=fake_inner),
            patch.object(main, "_emit_job_event", side_effect=lambda _j, event, _d: events.append(event)),
        ):
            await main._run_job("job-no-warning", _request())

    asyncio.run(scenario())
    assert store.get_job("job-no-warning")["status"] == "completed"
    assert events == ["job.completed"]


def test_unexpected_inner_exception_marks_job_failed():
    store = InMemoryJobStore()
    events: list[tuple[str, dict]] = []
    store.set_job("job-2", status="running", error=None)

    async def failing_inner(*_args, **_kwargs):
        raise RuntimeError("model unavailable")

    def capture_event(_job_id: str, event: str, data: dict) -> None:
        events.append((event, data))

    async def scenario() -> None:
        with (
            patch.object(main, "_job_store_instance", store),
            patch.object(main, "_JOB_TIMEOUT", 1),
            patch.object(main, "_run_job_inner", side_effect=failing_inner),
            patch.object(main, "_emit_job_event", side_effect=capture_event),
            patch.object(main, "get_db_ctx", side_effect=RuntimeError("db disabled")),
        ):
            await main._run_job("job-2", _request())

    asyncio.run(scenario())

    job = store.get_job("job-2")
    assert [event for event, _ in events] == ["job.failed"]
    assert job["status"] == "failed"
    assert job["error"] == "RuntimeError: model unavailable"
    assert job["overtime"] is False


def test_overtime_job_that_later_raises_finishes_as_failed():
    store = InMemoryJobStore()
    events: list[str] = []

    async def failing_inner(*_args, **_kwargs):
        await asyncio.sleep(0.02)
        raise RuntimeError("late failure")

    async def scenario() -> None:
        with (
            patch.object(main, "_job_store_instance", store),
            patch.object(main, "_JOB_TIMEOUT", 0.01),
            patch.object(main, "_run_job_inner", side_effect=failing_inner),
            patch.object(main, "_emit_job_event", side_effect=lambda _j, event, _d: events.append(event)),
            patch.object(main, "get_db_ctx", side_effect=RuntimeError("db disabled")),
        ):
            await main._run_job("job-late-failure", _request())

    asyncio.run(scenario())
    job = store.get_job("job-late-failure")
    assert events == ["job.overtime", "job.failed"]
    assert job["status"] == "failed"
    assert job["error"] == "RuntimeError: late failure"
    assert job["overtime"] is False
    assert job["overtime_at"] is None


def test_report_save_failure_is_raised_to_the_job_failure_boundary():
    def failing_save():
        raise OSError("disk full")

    async def scenario() -> None:
        try:
            await main._save_report_or_raise("job-db", failing_save, stage="save")
        except RuntimeError as exc:
            assert "Failed to save report for job job-db" in str(exc)
            assert isinstance(exc.__cause__, OSError)
        else:
            raise AssertionError("report persistence errors must not be swallowed")

    asyncio.run(scenario())
