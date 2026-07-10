from __future__ import annotations

import asyncio
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from scheduler import main as scheduler_main


def test_scheduled_slot_and_success_wait_for_analysis_terminal_outcome():
    """A long analysis must retain its scheduler slot until `_run_job` returns.

    The production `_run_job` emits the soft overtime notification while it
    continues awaiting its inner task.  This scheduler-level regression test
    verifies that downstream success recording and notifications cannot run at
    that intermediate point, and that a queued analysis cannot acquire the
    released slot early.
    """

    async def scenario() -> None:
        scheduler_main._semaphore = asyncio.Semaphore(1)
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        release_first = asyncio.Event()
        call_order: list[str] = []

        async def fake_run_job(job_id, *_args, **_kwargs):
            call_order.append(f"start:{job_id}")
            if job_id == "job-first":
                first_started.set()
                await release_first.wait()
            else:
                second_started.set()
            call_order.append(f"finish:{job_id}")

        mark_success = Mock(side_effect=lambda *_args, **_kwargs: call_order.append("success"))
        send_notifications = AsyncMock(
            side_effect=lambda *_args, **_kwargs: call_order.append("notify")
        )

        task_data = {
            "id": "schedule-1",
            "user_id": "user-1",
            "symbol": "600519.SH",
            "horizon": "short",
            # Keep this truthy so the scheduler does not enter the unrelated
            # imported-portfolio DB lookup path in this lifecycle-only test.
            "manual_user_context": {"objective": "lifecycle regression"},
        }

        with (
            patch.object(
                scheduler_main,
                "get_db_ctx",
                side_effect=lambda: nullcontext(SimpleNamespace()),
            ),
            patch.object(
                scheduler_main,
                "_build_scheduled_analyze_request",
                return_value=SimpleNamespace(symbol="600519.SH"),
            ),
            patch.object(scheduler_main, "_run_job", side_effect=fake_run_job),
            patch.object(scheduler_main, "_get_job", return_value={"status": "completed"}),
            patch.object(scheduler_main.scheduled_service, "mark_run_success", mark_success),
            patch.object(
                scheduler_main,
                "_send_scheduled_report_notifications",
                send_notifications,
            ),
        ):
            first = asyncio.create_task(
                scheduler_main._run_scheduled_analysis_once(
                    task_data,
                    "2026-07-10",
                    "job-first",
                    mark_schedule_run=True,
                )
            )
            await first_started.wait()

            second = asyncio.create_task(
                scheduler_main._run_scheduled_analysis_once(
                    task_data,
                    "2026-07-10",
                    "job-second",
                    mark_schedule_run=True,
                )
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            assert not first.done()
            assert not second_started.is_set()
            mark_success.assert_not_called()
            send_notifications.assert_not_awaited()

            release_first.set()
            await asyncio.gather(first, second)

        assert second_started.is_set()
        assert mark_success.call_count == 2
        assert send_notifications.await_count == 2
        assert call_order.index("finish:job-first") < call_order.index("start:job-second")
        assert call_order.index("finish:job-first") < call_order.index("success")
        assert call_order.index("success") < call_order.index("notify")

    asyncio.run(scenario())
