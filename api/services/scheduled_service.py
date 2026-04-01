"""Scheduled analysis service for database operations."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from api.database import ScheduledAnalysisDB
from tradingagents.dataflows.trade_calendar import is_cn_trading_day

VALID_HORIZONS = {"short", "medium"}
VALID_TASK_TYPES = {"market_window", "custom_recurring"}
VALID_PROMPT_MODES = {"merge_global", "override_global"}
VALID_FREQUENCIES = {"trading_day", "daily", "weekly", "monthly"}
MARKET_WINDOW_SLOTS = {
    "pre_open_0800": {"time": "08:00", "label": "开盘前"},
    "midday_1200": {"time": "12:00", "label": "午间"},
    "post_close_2000": {"time": "20:00", "label": "收盘后"},
}
CUSTOM_SLOTS = {
    "custom_short": {"horizon": "short", "label": "自定义短线"},
    "custom_long": {"horizon": "medium", "label": "自定义长期"},
}
TASK_SLOT_META = {**MARKET_WINDOW_SLOTS, **CUSTOM_SLOTS}
MAX_SCHEDULED_ITEMS = 5


def _parse_ymd(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _validate_trigger_time(t: str) -> str:
    """Validate HH:MM format. Allowed: 20:00~23:59 or 00:00~08:00 or exactly 12:00."""
    parts = t.strip().split(":")
    if len(parts) != 2:
        raise ValueError("时间格式错误，请使用 HH:MM")
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError("时间格式错误，请使用 HH:MM") from exc
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("时间格式错误，请使用 HH:MM")
    time_val = hh * 60 + mm
    if time_val == 12 * 60:
        return f"{hh:02d}:{mm:02d}"
    if 8 * 60 < time_val < 20 * 60:
        raise ValueError("定时时间仅允许 20:00~次日 08:00，或固定午间 12:00")
    return f"{hh:02d}:{mm:02d}"


def _slot_label(task_slot: str) -> str:
    return TASK_SLOT_META.get(task_slot, {}).get("label", task_slot)


def _validate_slot(task_type: str, task_slot: str) -> None:
    if task_type == "market_window":
        if task_slot not in MARKET_WINDOW_SLOTS:
            raise ValueError("交易日窗口任务槽位无效")
        return
    if task_type == "custom_recurring":
        if task_slot not in CUSTOM_SLOTS:
            raise ValueError("自定义任务槽位无效")
        return
    raise ValueError("task_type 必须为 market_window 或 custom_recurring")


def _normalize_create_payload(
    *,
    task_type: str,
    task_slot: str,
    frequency: Optional[str],
    horizon: Optional[str],
    trigger_time: Optional[str],
    day_of_week: Optional[int],
    day_of_month: Optional[int],
    prompt_mode: str,
    custom_prompt: Optional[str],
) -> Dict[str, Any]:
    if task_type not in VALID_TASK_TYPES:
        raise ValueError("task_type 必须为 market_window 或 custom_recurring")
    _validate_slot(task_type, task_slot)

    if prompt_mode not in VALID_PROMPT_MODES:
        raise ValueError("prompt_mode 必须为 merge_global 或 override_global")

    custom_prompt = (custom_prompt or "").strip() or None

    if task_type == "market_window":
        normalized_frequency = "trading_day"
        normalized_horizon = "short"
        normalized_trigger_time = MARKET_WINDOW_SLOTS[task_slot]["time"]
        normalized_day_of_week = None
        normalized_day_of_month = None
    else:
        normalized_frequency = (frequency or "daily").strip()
        if normalized_frequency not in {"daily", "weekly", "monthly"}:
            raise ValueError("自定义任务频率必须为 daily、weekly 或 monthly")
        normalized_horizon = CUSTOM_SLOTS[task_slot]["horizon"]
        normalized_trigger_time = _validate_trigger_time(trigger_time or "20:00")
        normalized_day_of_week = None
        normalized_day_of_month = None
        if normalized_frequency == "weekly":
            if day_of_week is None or not (0 <= int(day_of_week) <= 6):
                raise ValueError("weekly 任务需要 day_of_week，范围为 0-6")
            normalized_day_of_week = int(day_of_week)
        elif normalized_frequency == "monthly":
            if day_of_month is None or not (1 <= int(day_of_month) <= 31):
                raise ValueError("monthly 任务需要 day_of_month，范围为 1-31")
            normalized_day_of_month = int(day_of_month)

    if normalized_horizon not in VALID_HORIZONS:
        raise ValueError("horizon 必须为 short 或 medium")

    return {
        "task_type": task_type,
        "task_slot": task_slot,
        "frequency": normalized_frequency,
        "horizon": normalized_horizon,
        "trigger_time": normalized_trigger_time,
        "day_of_week": normalized_day_of_week,
        "day_of_month": normalized_day_of_month,
        "prompt_mode": prompt_mode,
        "custom_prompt": custom_prompt,
    }


def _period_key(freq: str, current_date: date) -> str:
    if freq in {"trading_day", "daily"}:
        return current_date.strftime("%Y-%m-%d")
    if freq == "weekly":
        iso = current_date.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return current_date.strftime("%Y-%m")


def _monthly_due_date(year: int, month: int, day_of_month: int) -> date:
    last_day = monthrange(year, month)[1]
    candidate = date(year, month, min(day_of_month, last_day))
    cur = candidate
    while cur.month == month:
        if is_cn_trading_day(cur.strftime("%Y-%m-%d")):
            return cur
        cur -= timedelta(days=1)
    cur = candidate + timedelta(days=1)
    while cur.month == month:
        if is_cn_trading_day(cur.strftime("%Y-%m-%d")):
            return cur
        cur += timedelta(days=1)
    return candidate


def _task_matches_date(task: ScheduledAnalysisDB, current_date: date) -> bool:
    current_ymd = current_date.strftime("%Y-%m-%d")
    if task.task_type == "market_window":
        return is_cn_trading_day(current_ymd)
    if task.frequency == "daily":
        return True
    if task.frequency == "weekly":
        return task.day_of_week == current_date.weekday()
    if task.frequency == "monthly":
        if not task.day_of_month:
            return False
        return _monthly_due_date(current_date.year, current_date.month, task.day_of_month) == current_date
    return False


def list_scheduled(db: Session, user_id: str) -> List[dict]:
    """List user's scheduled analysis tasks."""
    items = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.user_id == user_id)
        .order_by(ScheduledAnalysisDB.symbol, ScheduledAnalysisDB.task_slot, ScheduledAnalysisDB.created_at)
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
    if "prompt_mode" in kwargs:
        prompt_mode = kwargs["prompt_mode"]
        if prompt_mode not in VALID_PROMPT_MODES:
            raise ValueError("prompt_mode 必须为 merge_global 或 override_global")
        item.prompt_mode = prompt_mode
    if "custom_prompt" in kwargs:
        item.custom_prompt = (kwargs["custom_prompt"] or "").strip() or None

    if item.task_type == "custom_recurring":
        if "horizon" in kwargs:
            horizon = _validate_horizon(kwargs["horizon"])
            item.horizon = horizon
            item.task_slot = "custom_long" if horizon == "medium" else "custom_short"
        if "frequency" in kwargs:
            frequency = kwargs["frequency"]
            if frequency not in {"daily", "weekly", "monthly"}:
                raise ValueError("自定义任务频率必须为 daily、weekly 或 monthly")
            item.frequency = frequency
            if frequency != "weekly":
                item.day_of_week = None
            if frequency != "monthly":
                item.day_of_month = None
        if "trigger_time" in kwargs:
            item.trigger_time = _validate_trigger_time(kwargs["trigger_time"])
        if "day_of_week" in kwargs:
            value = kwargs["day_of_week"]
            if value is None:
                item.day_of_week = None
            elif not (0 <= int(value) <= 6):
                raise ValueError("day_of_week 范围必须为 0-6")
            else:
                item.day_of_week = int(value)
        if "day_of_month" in kwargs:
            value = kwargs["day_of_month"]
            if value is None:
                item.day_of_month = None
            elif not (1 <= int(value) <= 31):
                raise ValueError("day_of_month 范围必须为 1-31")
            else:
                item.day_of_month = int(value)
        if item.frequency == "weekly" and item.day_of_week is None:
            raise ValueError("weekly 任务需要 day_of_week，范围为 0-6")
        if item.frequency == "monthly" and item.day_of_month is None:
            raise ValueError("monthly 任务需要 day_of_month，范围为 1-31")
    else:
        item.frequency = "trading_day"
        item.trigger_time = MARKET_WINDOW_SLOTS[item.task_slot]["time"]
        item.day_of_week = None
        item.day_of_month = None
        item.horizon = "short"


def create_scheduled(
    db: Session,
    user_id: str,
    symbol: str,
    *,
    task_type: str,
    task_slot: str,
    frequency: Optional[str] = None,
    horizon: Optional[str] = None,
    trigger_time: Optional[str] = None,
    day_of_week: Optional[int] = None,
    day_of_month: Optional[int] = None,
    prompt_mode: str = "merge_global",
    custom_prompt: Optional[str] = None,
) -> dict:
    """Create a scheduled analysis task."""
    normalized = _normalize_create_payload(
        task_type=task_type,
        task_slot=task_slot,
        frequency=frequency,
        horizon=horizon,
        trigger_time=trigger_time,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        prompt_mode=prompt_mode,
        custom_prompt=custom_prompt,
    )

    existing = (
        db.query(ScheduledAnalysisDB)
        .filter(
            ScheduledAnalysisDB.user_id == user_id,
            ScheduledAnalysisDB.symbol == symbol,
            ScheduledAnalysisDB.task_slot == normalized["task_slot"],
        )
        .first()
    )
    if existing:
        raise ValueError(f"{symbol} 的 {_slot_label(normalized['task_slot'])} 任务已存在")

    item = ScheduledAnalysisDB(
        id=uuid4().hex,
        user_id=user_id,
        symbol=symbol,
        **normalized,
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
    """Ensure each symbol has a default post-close scheduled task."""

    existing_items = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.user_id == user_id)
        .order_by(ScheduledAnalysisDB.created_at)
        .all()
    )
    existing_pairs = {(item.symbol, item.task_slot) for item in existing_items}

    created: list[str] = []
    existing: list[str] = []
    skipped_limit: list[str] = []
    seen: set[str] = set()

    for raw_symbol in symbols:
        symbol = (raw_symbol or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)

        slot_pair = (symbol, "post_close_2000")
        if slot_pair in existing_pairs:
            existing.append(symbol)
            continue

        db.add(
            ScheduledAnalysisDB(
                id=uuid4().hex,
                user_id=user_id,
                symbol=symbol,
                task_type="market_window",
                task_slot="post_close_2000",
                frequency="trading_day",
                horizon="short",
                trigger_time="20:00",
                prompt_mode="merge_global",
            )
        )
        existing_pairs.add(slot_pair)
        created.append(symbol)

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

    if "horizon" in kwargs and item.task_type == "custom_recurring":
        target_horizon = _validate_horizon(kwargs["horizon"])
        target_slot = "custom_long" if target_horizon == "medium" else "custom_short"
        duplicate = (
            db.query(ScheduledAnalysisDB)
            .filter(
                ScheduledAnalysisDB.user_id == user_id,
                ScheduledAnalysisDB.symbol == item.symbol,
                ScheduledAnalysisDB.task_slot == target_slot,
                ScheduledAnalysisDB.id != item.id,
            )
            .first()
        )
        if duplicate:
            raise ValueError(f"{item.symbol} 的 {_slot_label(target_slot)} 任务已存在")

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
        item = item_map[item_id]
        if "horizon" in kwargs and item.task_type == "custom_recurring":
            target_horizon = _validate_horizon(kwargs["horizon"])
            target_slot = "custom_long" if target_horizon == "medium" else "custom_short"
            duplicate = (
                db.query(ScheduledAnalysisDB)
                .filter(
                    ScheduledAnalysisDB.user_id == user_id,
                    ScheduledAnalysisDB.symbol == item.symbol,
                    ScheduledAnalysisDB.task_slot == target_slot,
                    ScheduledAnalysisDB.id != item.id,
                )
                .first()
            )
            if duplicate:
                raise ValueError(f"{item.symbol} 的 {_slot_label(target_slot)} 任务已存在")
        _apply_scheduled_updates(item, **kwargs)

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


def get_pending_tasks(db: Session, current_date_str: str, current_hhmm: str) -> List[ScheduledAnalysisDB]:
    """Get all active tasks whose cycle is due and trigger time has passed."""
    current_date = _parse_ymd(current_date_str)
    all_active = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.is_active == True)
        .all()
    )
    pending: List[ScheduledAnalysisDB] = []
    for task in all_active:
        if not _task_matches_date(task, current_date):
            continue
        if (task.trigger_time or "20:00") > current_hhmm:
            continue
        run_key = _period_key(task.frequency or "daily", current_date)
        if task.last_run_key == run_key:
            continue
        pending.append(task)
    return pending


def current_run_key(task: ScheduledAnalysisDB, trade_date: str) -> str:
    return _period_key(task.frequency or "daily", _parse_ymd(trade_date))


def mark_run_success(db: Session, item_id: str, trade_date: str, report_id: str):
    """Mark a scheduled task as successfully run."""
    item = db.query(ScheduledAnalysisDB).filter(ScheduledAnalysisDB.id == item_id).first()
    if item:
        run_date = _parse_ymd(trade_date)
        item.last_run_key = _period_key(item.frequency or "daily", run_date)
        item.last_run_date = trade_date
        item.last_run_status = "success"
        item.last_report_id = report_id
        item.consecutive_failures = 0
        db.commit()


def mark_run_failed(db: Session, item_id: str, trade_date: str):
    """Mark a scheduled task as failed. Auto-deactivate after 3 consecutive failures."""
    item = db.query(ScheduledAnalysisDB).filter(ScheduledAnalysisDB.id == item_id).first()
    if item:
        run_date = _parse_ymd(trade_date)
        item.last_run_key = _period_key(item.frequency or "daily", run_date)
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
        "task_type": item.task_type,
        "task_slot": item.task_slot,
        "task_label": _slot_label(item.task_slot),
        "frequency": item.frequency,
        "horizon": item.horizon or "short",
        "trigger_time": item.trigger_time or "20:00",
        "day_of_week": item.day_of_week,
        "day_of_month": item.day_of_month,
        "prompt_mode": item.prompt_mode or "merge_global",
        "custom_prompt": item.custom_prompt,
        "is_active": item.is_active,
        "last_run_key": item.last_run_key,
        "last_run_date": item.last_run_date,
        "last_run_status": item.last_run_status,
        "last_report_id": item.last_report_id,
        "consecutive_failures": item.consecutive_failures,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
