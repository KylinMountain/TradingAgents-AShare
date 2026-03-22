"""Scheduled analysis service for database operations."""

from typing import List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from api.database import ScheduledAnalysisDB

MAX_SCHEDULED_ITEMS = 10

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

    if horizon not in VALID_HORIZONS:
        raise ValueError(f"horizon 必须为 short 或 medium")

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


def update_scheduled(db: Session, user_id: str, item_id: str, **kwargs) -> Optional[dict]:
    """Update a scheduled analysis task. Returns None if not found."""
    item = (
        db.query(ScheduledAnalysisDB)
        .filter(ScheduledAnalysisDB.id == item_id, ScheduledAnalysisDB.user_id == user_id)
        .first()
    )
    if not item:
        return None

    if "is_active" in kwargs:
        item.is_active = kwargs["is_active"]
        if kwargs["is_active"]:
            item.consecutive_failures = 0
    if "horizon" in kwargs:
        if kwargs["horizon"] not in VALID_HORIZONS:
            raise ValueError("horizon 必须为 short 或 medium")
        item.horizon = kwargs["horizon"]
    if "trigger_time" in kwargs:
        item.trigger_time = _validate_trigger_time(kwargs["trigger_time"])

    db.commit()
    db.refresh(item)
    return _to_dict(item)


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


def get_pending_tasks(db: Session, today: str, current_hhmm: str) -> List[ScheduledAnalysisDB]:
    """Get all active tasks that haven't run today and whose trigger time has passed."""
    all_active = (
        db.query(ScheduledAnalysisDB)
        .filter(
            ScheduledAnalysisDB.is_active == True,
            (ScheduledAnalysisDB.last_run_date != today) | (ScheduledAnalysisDB.last_run_date == None),
        )
        .all()
    )
    # Filter by trigger_time <= current_hhmm
    return [t for t in all_active if (t.trigger_time or "20:00") <= current_hhmm]


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
