"""Scheduled analysis service for database operations."""

import hashlib
import logging
import os
from typing import Iterable, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from api.database import ScheduledAnalysisDB

logger = logging.getLogger(__name__)

MAX_SCHEDULED_ITEMS = 10

# Maximum jitter (minutes) added to trigger_time to spread concurrent tasks.
# Each task gets a deterministic offset (0 ~ JITTER_MAX) per day so the same
# task always fires at the same jittered time on a given date.
JITTER_MAX_MINUTES = int(os.getenv("TA_SCHEDULED_JITTER_MINUTES", "30"))

# 非交易时间窗口：15:00~次日9:15 允许设置
VALID_HORIZONS = {"short", "medium"}


def _validate_trigger_time(t: str) -> str:
    """Validate HH:MM format. Allowed: 20:00~23:59 or 00:00~08:00."""
    parts = t.strip().split(":")
    if len(parts) != 2:
        raise ValueError("时间格式错误，请使用 HH:MM")
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError("时间格式错误，请使用 HH:MM")
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("时间格式错误，请使用 HH:MM")
    time_val = hh * 60 + mm
    # Allowed: 20:00 (1200) ~ 23:59 (1439) or 00:00 (0) ~ 08:00 (480)
    if 8 * 60 < time_val < 20 * 60:
        raise ValueError("定时时间仅允许 20:00~次日 08:00（避免影响白天使用）")
    return f"{hh:02d}:{mm:02d}"


def list_scheduled(db: Session, user_id: str) -> List[dict]:
    """List user's scheduled analysis tasks."""
    items = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.user_id == user_id)
        .order_by(ScheduledAnalysisDB.created_at)
        .all()
    )
    return [_to_dict(item) for item in items]


def get_scheduled(db: Session, user_id: str, item_id: str) -> Optional[dict]:
    """Get a single scheduled analysis task for the user."""
    item = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.user_id == user_id, ScheduledAnalysisDB.id == item_id)
        .first()
    )
    if not item:
        return None
    return _to_dict(item)


def get_scheduled_batch(db: Session, user_id: str, item_ids: Iterable[str]) -> List[dict]:
    """Get multiple scheduled analysis tasks in the requested order."""

    normalized_ids = _normalize_item_ids(item_ids)
    if not normalized_ids:
        raise ValueError("请至少选择一个定时任务")

    items = (
        db.query(ScheduledAnalysisDB)
        .filter(
            ScheduledAnalysisDB.user_id == user_id,
            ScheduledAnalysisDB.id.in_(normalized_ids),
        )
        .all()
    )
    item_map = {item.id: item for item in items}
    missing_ids = [item_id for item_id in normalized_ids if item_id not in item_map]
    if missing_ids:
        raise ValueError("部分定时任务不存在或已失效，请刷新后重试")

    return [_to_dict(item_map[item_id]) for item_id in normalized_ids]


def _normalize_item_ids(item_ids: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_id in item_ids:
        item_id = (raw_id or "").strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        normalized.append(item_id)
    return normalized


def _validate_horizon(horizon: str) -> str:
    if horizon not in VALID_HORIZONS:
        raise ValueError("horizon 必须为 short 或 medium")
    return horizon


def _apply_scheduled_updates(item: ScheduledAnalysisDB, **kwargs) -> None:
    if "is_active" in kwargs:
        item.is_active = kwargs["is_active"]
        if kwargs["is_active"]:
            item.consecutive_failures = 0
    if "horizon" in kwargs:
        item.horizon = _validate_horizon(kwargs["horizon"])
    if "trigger_time" in kwargs:
        item.trigger_time = _validate_trigger_time(kwargs["trigger_time"])


def create_scheduled(
    db: Session,
    user_id: str,
    symbol: str,
    horizon: str = "short",
    trigger_time: str = "20:00",
) -> dict:
    """Create a scheduled analysis task."""
    count = db.query(ScheduledAnalysisDB).filter(
        ScheduledAnalysisDB.user_id == user_id
    ).count()
    if count >= MAX_SCHEDULED_ITEMS:
        raise ValueError(f"定时分析数量已达上限 ({MAX_SCHEDULED_ITEMS})")

    existing = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.user_id == user_id, ScheduledAnalysisDB.symbol == symbol)
        .first()
    )
    if existing:
        raise ValueError(f"{symbol} 已有定时分析任务")

    horizon = _validate_horizon(horizon)

    trigger_time = _validate_trigger_time(trigger_time)

    item = ScheduledAnalysisDB(
        id=uuid4().hex,
        user_id=user_id,
        symbol=symbol,
        horizon=horizon,
        trigger_time=trigger_time,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_dict(item)


def ensure_scheduled_for_symbols(
    db: Session,
    user_id: str,
    symbols: Iterable[str],
    horizon: str = "short",
    trigger_time: str = "20:00",
) -> dict:
    """Ensure the given symbols exist in scheduled tasks without duplicating existing items."""

    horizon = _validate_horizon(horizon)

    trigger_time = _validate_trigger_time(trigger_time)

    existing_items = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.user_id == user_id)
        .order_by(ScheduledAnalysisDB.created_at)
        .all()
    )
    existing_symbols = {item.symbol for item in existing_items}
    remaining_slots = max(0, MAX_SCHEDULED_ITEMS - len(existing_items))

    created: list[str] = []
    existing: list[str] = []
    skipped_limit: list[str] = []
    seen: set[str] = set()

    for raw_symbol in symbols:
        symbol = (raw_symbol or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)

        if symbol in existing_symbols:
            existing.append(symbol)
            continue

        if remaining_slots <= 0:
            skipped_limit.append(symbol)
            continue

        db.add(
            ScheduledAnalysisDB(
                id=uuid4().hex,
                user_id=user_id,
                symbol=symbol,
                horizon=horizon,
                trigger_time=trigger_time,
            )
        )
        existing_symbols.add(symbol)
        created.append(symbol)
        remaining_slots -= 1

    if created:
        db.flush()

    return {
        "created": created,
        "existing": existing,
        "skipped_limit": skipped_limit,
    }


def update_scheduled(db: Session, user_id: str, item_id: str, **kwargs) -> Optional[dict]:
    """Update a scheduled analysis task. Returns None if not found."""
    item = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.id == item_id, ScheduledAnalysisDB.user_id == user_id)
        .first()
    )
    if not item:
        return None

    _apply_scheduled_updates(item, **kwargs)

    db.commit()
    db.refresh(item)
    return _to_dict(item)


def batch_update_scheduled(
    db: Session,
    user_id: str,
    item_ids: Iterable[str],
    **kwargs,
) -> List[dict]:
    """Update multiple scheduled analysis tasks in a single transaction."""

    normalized_ids = _normalize_item_ids(item_ids)
    if not normalized_ids:
        raise ValueError("请至少选择一个定时任务")
    if not kwargs:
        raise ValueError("至少提供一个更新字段")

    items = (
        db.query(ScheduledAnalysisDB)
        .filter(
            ScheduledAnalysisDB.user_id == user_id,
            ScheduledAnalysisDB.id.in_(normalized_ids),
        )
        .all()
    )
    item_map = {item.id: item for item in items}
    missing_ids = [item_id for item_id in normalized_ids if item_id not in item_map]
    if missing_ids:
        raise ValueError("部分定时任务不存在或已失效，请刷新后重试")

    for item_id in normalized_ids:
        _apply_scheduled_updates(item_map[item_id], **kwargs)

    db.commit()
    for item in items:
        db.refresh(item)
    return [_to_dict(item_map[item_id]) for item_id in normalized_ids]


def delete_scheduled(db: Session, user_id: str, item_id: str) -> bool:
    """Delete a scheduled analysis task."""
    item = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.id == item_id, ScheduledAnalysisDB.user_id == user_id)
        .first()
    )
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def batch_delete_scheduled(db: Session, user_id: str, item_ids: Iterable[str]) -> dict:
    """Delete multiple scheduled analysis tasks."""

    normalized_ids = _normalize_item_ids(item_ids)
    if not normalized_ids:
        raise ValueError("请至少选择一个定时任务")

    items = (
        db.query(ScheduledAnalysisDB)
        .filter(
            ScheduledAnalysisDB.user_id == user_id,
            ScheduledAnalysisDB.id.in_(normalized_ids),
        )
        .all()
    )
    item_map = {item.id: item for item in items}
    deleted_ids: list[str] = []
    missing_ids: list[str] = []

    for item_id in normalized_ids:
        item = item_map.get(item_id)
        if item is None:
            missing_ids.append(item_id)
            continue
        db.delete(item)
        deleted_ids.append(item_id)

    if deleted_ids:
        db.commit()

    return {
        "deleted_ids": deleted_ids,
        "missing_ids": missing_ids,
    }


def _compute_jitter_minutes(task_id: str, today: str) -> int:
    """Return a deterministic jitter in [0, JITTER_MAX_MINUTES] for a task on a given date."""
    if JITTER_MAX_MINUTES <= 0:
        return 0
    digest = hashlib.md5(f"{task_id}:{today}".encode()).hexdigest()
    return int(digest, 16) % (JITTER_MAX_MINUTES + 1)


def _add_minutes_to_hhmm(hhmm: str, minutes: int) -> str:
    """Add *minutes* to an HH:MM string. Clamps at 23:59 (no day wrap)."""
    parts = hhmm.split(":")
    total = int(parts[0]) * 60 + int(parts[1]) + minutes
    if total >= 24 * 60:
        total = 23 * 60 + 59
    return f"{total // 60:02d}:{total % 60:02d}"


def get_pending_tasks(db: Session, today: str, current_hhmm: str) -> List[ScheduledAnalysisDB]:
    """Get all active tasks that haven't run today and whose jittered trigger time has passed.

    Each task's effective trigger time = trigger_time + deterministic jitter,
    so tasks configured at the same time are automatically spread over a
    window of ``JITTER_MAX_MINUTES`` (default 30 min, env ``TA_SCHEDULED_JITTER_MINUTES``).
    """
    all_active = (
        db.query(ScheduledAnalysisDB)
        .filter(
            ScheduledAnalysisDB.is_active == True,
            (ScheduledAnalysisDB.last_run_date != today) | (ScheduledAnalysisDB.last_run_date == None),
        )
        .all()
    )
    result = []
    for t in all_active:
        base_time = t.trigger_time or "20:00"
        jitter = _compute_jitter_minutes(t.id, today)
        effective_time = _add_minutes_to_hhmm(base_time, jitter)
        if effective_time <= current_hhmm:
            result.append(t)
        else:
            logger.debug(
                "[Scheduler] %s deferred: base=%s jitter=+%dm effective=%s (now=%s)",
                t.symbol, base_time, jitter, effective_time, current_hhmm,
            )
    return result


def mark_run_success(db: Session, item_id: str, trade_date: str, report_id: str):
    """Mark a scheduled task as successfully run."""
    item = db.query(ScheduledAnalysisDB).filter(ScheduledAnalysisDB.id == item_id).first()
    if item:
        item.last_run_date = trade_date
        item.last_run_status = "success"
        item.last_report_id = report_id
        item.consecutive_failures = 0
        db.commit()


def mark_run_failed(db: Session, item_id: str, trade_date: str):
    """Mark a scheduled task as failed. Auto-deactivate after 3 consecutive failures."""
    item = db.query(ScheduledAnalysisDB).filter(ScheduledAnalysisDB.id == item_id).first()
    if item:
        item.last_run_date = trade_date
        item.last_run_status = "failed"
        item.consecutive_failures = (item.consecutive_failures or 0) + 1
        if item.consecutive_failures >= 3:
            item.is_active = False
        db.commit()


def record_manual_test_result(
    db: Session,
    item_id: str,
    status: str,
    report_id: Optional[str] = None,
) -> None:
    """Record the latest manual test result without consuming the day's schedule."""
    item = db.query(ScheduledAnalysisDB).filter(ScheduledAnalysisDB.id == item_id).first()
    if not item:
        return
    item.last_run_status = status
    if report_id:
        item.last_report_id = report_id
    if status == "success":
        item.consecutive_failures = 0
    db.commit()


def _to_dict(item: ScheduledAnalysisDB) -> dict:
    return {
        "id": item.id,
        "symbol": item.symbol,
        "horizon": item.horizon or "short",
        "trigger_time": item.trigger_time or "15:30",
        "is_active": item.is_active,
        "last_run_date": item.last_run_date,
        "last_run_status": item.last_run_status,
        "last_report_id": item.last_report_id,
        "consecutive_failures": item.consecutive_failures,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
