"""Standalone scheduler process.

Runs independently of the FastAPI API server. Checks every minute for
scheduled analysis tasks to trigger and executes them with concurrency
control via a simple ``asyncio.Semaphore``.

Start with::

    python -m scheduler.main
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _log(msg: str):
    logger.info(msg)


# ── Concurrency ──────────────────────────────────────────────────────────────
SCHEDULER_CONCURRENCY = int(os.getenv("SCHEDULER_CONCURRENCY", "3"))

_semaphore: Optional[asyncio.Semaphore] = None
_executor: Optional[ThreadPoolExecutor] = None

# Hold references to fire-and-forget tasks so they are not garbage collected
_background_tasks: set = set()


def _create_tracked_task(coro, *, label: str = "Background task") -> asyncio.Task:
    """Create an asyncio task and keep a reference to prevent GC."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def _on_done(t: asyncio.Task):
        _background_tasks.discard(t)
        if not t.cancelled() and t.exception():
            logger.error("%s failed: %s", label, t.exception())

    task.add_done_callback(_on_done)
    return task


# ── Imports from api & tradingagents ─────────────────────────────────────────
from api.database import (
    ScheduledAnalysisDB,
    ReportDB,
    UserDB,
    init_db,
    get_db_ctx,
)
from api.job_store import get_job_store as _new_job_store
from api.services import (
    auth_service,
    report_service,
    scheduled_service,
)

# Thin wrappers & job runner from the API module
from api.main import (
    _build_imported_user_context,
    _build_scheduled_analyze_request,
    _resolve_scheduled_trade_date,
    _run_job,
    _set_job,
    _get_job,
    _emit_job_event,
    get_job_store,
)

from tradingagents.dataflows.providers.cn_akshare_provider import set_scheduled_task_context


# ── Semaphore-based concurrency slot ─────────────────────────────────────────

@asynccontextmanager
async def _concurrency_slot(job_id: str, symbol: str):
    """Acquire/release a concurrency slot for a scheduled job."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(SCHEDULER_CONCURRENCY)

    if SCHEDULER_CONCURRENCY <= 0:
        # 0 = unlimited concurrency
        yield
        return

    _log(
        f"[Scheduler] Waiting for slot job={job_id} symbol={symbol}"
    )
    await _semaphore.acquire()
    try:
        _log(
            f"[Scheduler] Acquired slot job={job_id} symbol={symbol}"
        )
        yield
    finally:
        _semaphore.release()
        _log(
            f"[Scheduler] Released slot job={job_id} symbol={symbol}"
        )


# ── Notification ─────────────────────────────────────────────────────────────

async def _send_scheduled_report_notifications(
    user_id: str, report_id: str, symbol: str
) -> None:
    """Send configured scheduled report notifications (email & WeCom)."""
    try:
        from api.services.email_report_service import send_report_email_with_retry
        from api.services.wecom_notification_service import send_report_message_with_retry

        email_user = None
        report_to_send = None
        webhook_url = None
        wecom_report_enabled = True
        with get_db_ctx() as db:
            user = db.query(UserDB).filter(UserDB.id == user_id).first()
            report = db.query(ReportDB).filter(ReportDB.id == report_id).first()
            user_cfg = auth_service.get_user_llm_config(db, user_id)
            webhook_url = auth_service.decrypt_secret(
                getattr(user_cfg, "wecom_webhook_encrypted", None)
            )
            if report:
                db.expunge(report)
                report_to_send = report
            if user:
                wecom_report_enabled = getattr(user, "wecom_report_enabled", True)
                if getattr(user, "email_report_enabled", True):
                    db.expunge(user)
                    email_user = user
        if email_user and report_to_send:
            _log(f"[Scheduler] Sending email report for {symbol} to {email_user.email}")
            _create_tracked_task(
                send_report_email_with_retry(email_user, report_to_send),
                label=f"Email notification task ({symbol})",
            )
        if report_to_send and webhook_url and wecom_report_enabled:
            _log(f"[Scheduler] Sending WeCom report for {symbol}")
            _create_tracked_task(
                send_report_message_with_retry(report_to_send, webhook_url),
                label=f"WeCom notification task ({symbol})",
            )
    except Exception as e:
        logger.warning(f"[Scheduler] Notification send failed for {symbol}: {e}")


# ── Single scheduled analysis execution ──────────────────────────────────────

async def _run_scheduled_analysis_once(
    task: dict,
    requested_trade_date: str,
    job_id: str,
    *,
    mark_schedule_run: bool,
) -> None:
    """Execute one scheduled analysis, optionally recording it as the daily run."""
    task_id = task["id"]
    user_id = task["user_id"]
    symbol = task["symbol"]
    horizon = task.get("horizon") or "short"

    actual_trade_date = _resolve_scheduled_trade_date(requested_trade_date)
    _log(f"[Scheduler] {symbol} trade_date={actual_trade_date} (requested={requested_trade_date})")

    set_scheduled_task_context(True)
    try:
        async with _concurrency_slot(job_id, symbol):
            with get_db_ctx() as db:
                scheduled_user_context = task.get("manual_user_context") or _build_imported_user_context(
                    db, user_id, symbol
                )
                req = _build_scheduled_analyze_request(
                    db=db,
                    user_id=user_id,
                    symbol=symbol,
                    horizon=horizon,
                    trade_date=actual_trade_date,
                    scheduled_user_context=scheduled_user_context,
                )

            await _run_job(
                job_id,
                req,
                False,
                True,
                user_id,
                "scheduled" if mark_schedule_run else "scheduled_manual",
            )
        job_state = _get_job(job_id)
        if job_state.get("status") == "failed":
            raise RuntimeError(job_state.get("error") or f"scheduled analysis job {job_id} failed")
        with get_db_ctx() as db:
            if mark_schedule_run:
                scheduled_service.mark_run_success(db, task_id, requested_trade_date, job_id)
            else:
                scheduled_service.record_manual_test_result(db, task_id, "success", report_id=job_id)
        _log(f"[Scheduler] Completed {symbol}")

        await _send_scheduled_report_notifications(user_id, job_id, symbol)
    except Exception as e:
        logger.error(f"[Scheduler] Failed {symbol}: {e}\n{traceback.format_exc()}")
        with get_db_ctx() as db:
            if mark_schedule_run:
                scheduled_service.mark_run_failed(db, task_id, requested_trade_date)
            else:
                scheduled_service.record_manual_test_result(db, task_id, "failed")


async def _run_scheduled_job(task: dict, trade_date: str):
    """Execute a single scheduled analysis job.

    Args:
        task: dict with keys id, user_id, symbol, horizon (plain values,
              not an ORM instance, to avoid DetachedInstanceError).
        trade_date: YYYY-MM-DD string.
    """
    user_id = task["user_id"]
    symbol = task["symbol"]

    _log(f"[Scheduler] Running {symbol} for user={user_id}")
    job_id = uuid4().hex
    try:
        await _run_scheduled_analysis_once(
            task,
            trade_date,
            job_id,
            mark_schedule_run=True,
        )
    finally:
        get_job_store().delete_job(job_id)


# ── Scheduler loop ───────────────────────────────────────────────────────────

async def _scheduler_loop():
    """Background loop: check every minute for scheduled tasks to trigger.

    Each task has its own trigger_time (HH:MM). The scheduler runs on trading
    days only, outside of trading hours (before 9:15 or after 15:00). Tasks
    are triggered when current time >= task.trigger_time and the task hasn't
    run today yet.
    """
    from tradingagents.dataflows.trade_calendar import is_cn_trading_day
    from zoneinfo import ZoneInfo

    _log("[Scheduler] Loop started.")
    while True:
        await asyncio.sleep(60)
        try:
            now = datetime.now(tz=ZoneInfo("Asia/Shanghai"))
            today = now.strftime("%Y-%m-%d")
            current_hhmm = now.strftime("%H:%M")

            if not is_cn_trading_day(today):
                continue
            time_val = now.hour * 60 + now.minute
            if 8 * 60 < time_val < 20 * 60:
                continue

            with get_db_ctx() as db:
                tasks = scheduled_service.get_pending_tasks(db, today, current_hhmm)
                if not tasks:
                    continue

                for task in tasks:
                    task.last_run_date = today
                    task.last_run_status = "running"
                db.commit()

                task_snapshots = [
                    {
                        "id": task.id,
                        "user_id": task.user_id,
                        "symbol": task.symbol,
                        "horizon": task.horizon,
                    }
                    for task in tasks
                ]

                _log(f"[Scheduler] Launching {len(task_snapshots)} tasks (staggered)")
                for i, snap in enumerate(task_snapshots):
                    if i > 0:
                        await asyncio.sleep(1)
                    _create_tracked_task(_run_scheduled_job(snap, today))

        except Exception as e:
            logger.error(f"[Scheduler] Error: {e}")


# ── Stale task recovery ──────────────────────────────────────────────────────

def _recover_stale_tasks():
    """Reset tasks stuck in 'running' state (from previous crash/restart)."""
    with get_db_ctx() as db:
        stale = (
            db.query(ScheduledAnalysisDB)
            .filter(ScheduledAnalysisDB.last_run_status == "running")
            .all()
        )
        if stale:
            recovered_count = 0
            reset_count = 0
            for item in stale:
                has_report = (
                    item.last_report_id
                    and item.last_run_date
                    and db.query(ReportDB)
                    .filter(
                        ReportDB.id == item.last_report_id,
                        ReportDB.status == "completed",
                        ReportDB.created_at >= item.last_run_date,
                    )
                    .first()
                )
                if has_report:
                    item.last_run_status = "success"
                    recovered_count += 1
                else:
                    item.last_run_status = "stale"
                    item.last_run_date = None
                    reset_count += 1
            db.commit()
            _log(
                f"[Scheduler] Reset {len(stale)} stale 'running' tasks on startup "
                f"(recovered={recovered_count}, reset_to_stale={reset_count})."
            )
        report_reset = report_service.recover_stale_active_reports(db)
        if report_reset["total"]:
            _log(
                "[Reports] Recovered %s stale active reports on startup (marked failed)."
                % report_reset["total"]
            )


# ── Startup / main ───────────────────────────────────────────────────────────

async def _startup():
    """Initialize DB, pre-load caches, recover stale tasks, then run the loop."""
    global _semaphore, _executor

    init_db()
    _log("Database initialized.")

    _semaphore = asyncio.Semaphore(SCHEDULER_CONCURRENCY)
    _log(f"[Scheduler] Concurrency limit set to {SCHEDULER_CONCURRENCY}")

    _executor = ThreadPoolExecutor(max_workers=SCHEDULER_CONCURRENCY + 2)

    # Recover stale tasks from previous run
    _recover_stale_tasks()

    # Pre-load trade calendar (uses mini_racer/V8 which is not thread-safe)
    from tradingagents.dataflows.trade_calendar import _load_cn_trade_dates

    _load_cn_trade_dates()
    _log("Trade calendar pre-loaded.")

    # Pre-load stock + ETF name map
    from api.main import _load_cn_stock_map

    await asyncio.to_thread(_load_cn_stock_map)
    _log("Stock map pre-loaded on startup.")

    # Run the scheduler loop (blocks until cancelled)
    await _scheduler_loop()


def main():
    """Entry point for ``python -m scheduler.main``."""
    _log("[Scheduler] Starting standalone scheduler process ...")
    try:
        asyncio.run(_startup())
    except KeyboardInterrupt:
        _log("[Scheduler] Stopped by user.")


# Alias for pyproject.toml script entry (must be sync)
sync_main = main


if __name__ == "__main__":
    main()
