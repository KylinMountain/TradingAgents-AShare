"""Generic portfolio position import service.

Manages imported holdings from any source. Positions are stored as snapshots
in ``ImportedPortfolioPositionDB`` with a configurable ``source`` tag.
No dependency on any specific broker SDK.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from api.database import ImportedPortfolioPositionDB
from api.services import scheduled_service
from tradingagents.agents.utils.context_utils import normalize_user_context


logger = logging.getLogger(__name__)

_CODE_RE = re.compile(r"^(\d{6})\.(SH|SZ|BJ)$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sync_positions(
    db: Session,
    user_id: str,
    positions: list[dict[str, Any]],
    source: str = "manual",
    auto_apply_scheduled: bool = True,
) -> dict[str, Any]:
    """Replace the position snapshot for *source* with *positions*.

    Each item in *positions* should contain at minimum ``symbol`` (e.g.
    ``"600519.SH"``).  Optional fields: ``name``, ``current_position``,
    ``available_position``, ``average_cost``, ``market_value``,
    ``current_position_pct``.
    """
    if not isinstance(positions, list):
        raise ValueError("positions 必须为列表")

    source = (source or "manual").strip()
    now = datetime.now(timezone.utc)

    # Normalize & deduplicate
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in positions:
        symbol = _normalize_code(raw.get("symbol"))
        if symbol is None:
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        cleaned.append({
            "symbol": symbol,
            "name": (raw.get("name") or "").strip() or None,
            "current_position": _to_float(raw.get("current_position")),
            "available_position": _to_float(raw.get("available_position")),
            "average_cost": _to_float(raw.get("average_cost")),
            "market_value": _to_float(raw.get("market_value")),
            "current_position_pct": _to_float(raw.get("current_position_pct")),
        })

    # Compute position_pct if not provided but market_value is available
    total_mv = sum(p["market_value"] or 0 for p in cleaned if (p["market_value"] or 0) > 0)
    if total_mv > 0:
        for p in cleaned:
            if p["current_position_pct"] is None and p["market_value"] and p["market_value"] > 0:
                p["current_position_pct"] = round((p["market_value"] / total_mv) * 100, 4)

    if not cleaned:
        raise ValueError("没有有效的持仓记录，请检查输入格式")

    # Replace snapshot for this source
    db.query(ImportedPortfolioPositionDB).filter(
        ImportedPortfolioPositionDB.user_id == user_id,
        ImportedPortfolioPositionDB.source == source,
    ).delete()

    for p in cleaned:
        db.add(ImportedPortfolioPositionDB(
            id=uuid4().hex,
            user_id=user_id,
            source=source,
            symbol=p["symbol"],
            security_name=p["name"],
            current_position=p["current_position"],
            available_position=p["available_position"],
            average_cost=p["average_cost"],
            market_value=p["market_value"],
            current_position_pct=p["current_position_pct"],
            trade_points_json=[],
            trade_points_count=0,
            latest_trade_at=None,
            latest_trade_action=None,
            last_imported_at=now,
        ))

    scheduled_sync: dict[str, list] = {"created": [], "existing": [], "skipped_limit": []}
    if auto_apply_scheduled:
        ordered = [p["symbol"] for p in cleaned if (p["current_position"] or 0) > 0]
        scheduled_sync = scheduled_service.ensure_scheduled_for_symbols(
            db=db,
            user_id=user_id,
            symbols=ordered,
        )

    db.commit()
    return get_import_state(db, user_id, scheduled_sync=scheduled_sync)


def get_import_state(
    db: Session,
    user_id: str,
    scheduled_sync: dict[str, Any] | None = None,
) -> dict[str, Any]:
    positions = list_imported_positions(db, user_id)
    return {
        "auto_apply_scheduled": True,
        "last_synced_at": _latest_imported_at(positions),
        "last_error": None,
        "summary": {"positions": len(positions)},
        "scheduled_sync": scheduled_sync or {"created": [], "existing": [], "skipped_limit": []},
        "positions": positions,
    }


def list_imported_positions(db: Session, user_id: str) -> list[dict[str, Any]]:
    """List all imported positions for a user, regardless of source."""
    rows = (
        db.query(ImportedPortfolioPositionDB)
        .filter(ImportedPortfolioPositionDB.user_id == user_id)
        .order_by(
            ImportedPortfolioPositionDB.market_value.desc(),
            ImportedPortfolioPositionDB.current_position.desc(),
            ImportedPortfolioPositionDB.symbol,
        )
        .all()
    )
    return [
        {
            "symbol": row.symbol,
            "name": row.security_name or row.symbol,
            "source": row.source,
            "current_position": row.current_position,
            "available_position": row.available_position,
            "average_cost": row.average_cost,
            "market_value": row.market_value,
            "current_position_pct": row.current_position_pct,
            "trade_points_count": row.trade_points_count or 0,
            "last_imported_at": row.last_imported_at.isoformat() if row.last_imported_at else None,
        }
        for row in rows
    ]


def build_scheduled_user_context(db: Session, user_id: str, symbol: str) -> dict[str, Any]:
    """Build user context for a scheduled analysis from any imported source."""
    row = (
        db.query(ImportedPortfolioPositionDB)
        .filter(
            ImportedPortfolioPositionDB.user_id == user_id,
            ImportedPortfolioPositionDB.symbol == (symbol or "").strip().upper(),
        )
        .first()
    )
    if not row:
        return {}

    payload: dict[str, Any] = {
        "objective": "持有处理" if (row.current_position or 0) > 0 else "观察",
        "current_position": row.current_position,
        "current_position_pct": row.current_position_pct,
        "average_cost": row.average_cost,
        "user_notes": f"来源：持仓导入（{row.source}）",
    }
    return normalize_user_context(payload)


def clear_imported_portfolio(db: Session, user_id: str) -> None:
    """Clear all imported positions for a user, regardless of source."""
    db.query(ImportedPortfolioPositionDB).filter(
        ImportedPortfolioPositionDB.user_id == user_id,
    ).delete()
    db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_code(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if _CODE_RE.match(text):
        return text
    if re.match(r"^\d{6}$", text):
        if text.startswith("6"):
            return f"{text}.SH"
        if text.startswith(("0", "3")):
            return f"{text}.SZ"
        if text.startswith(("4", "8")):
            return f"{text}.BJ"
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _latest_imported_at(positions: list[dict[str, Any]]) -> str | None:
    dates = [p["last_imported_at"] for p in positions if p.get("last_imported_at")]
    return max(dates) if dates else None
