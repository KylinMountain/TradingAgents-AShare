from __future__ import annotations

import importlib
import logging
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from api.database import ImportedPortfolioPositionDB, QmtImportConfigDB
from api.services import scheduled_service
from tradingagents.agents.utils.context_utils import normalize_user_context


SOURCE_NAME = "qmt_xtquant"
logger = logging.getLogger(__name__)


def sync_qmt_portfolio(
    db: Session,
    user_id: str,
    qmt_path: str,
    account_id: str,
    account_type: str = "STOCK",
    auto_apply_scheduled: bool = True,
) -> dict[str, Any]:
    """Query live holdings from QMT / xtquant and store them as the latest snapshot."""

    qmt_path = _validate_qmt_path(qmt_path)
    trader_mod, xttype_mod = _load_xtquant_modules()
    xt_trader_cls = getattr(trader_mod, "XtQuantTrader", None)
    stock_account_cls = getattr(xttype_mod, "StockAccount", None)
    if xt_trader_cls is None or stock_account_cls is None:
        raise ValueError("xtquant 缺少 XtQuantTrader 或 StockAccount，无法读取 QMT 持仓")

    trader = None
    try:
        session_id = int(uuid4().hex[:8], 16)
        trader = xt_trader_cls(qmt_path, session_id)
        if hasattr(trader, "start"):
            trader.start()
        connect_result = trader.connect()
        if connect_result not in (0, None):
            raise ValueError(f"QMT 连接失败，connect() 返回 {connect_result}")

        account = stock_account_cls(account_id, account_type)
        positions = trader.query_stock_positions(account) or []
        now = datetime.now(timezone.utc)
        total_market_value = sum(
            float(getattr(item, "market_value", 0) or 0)
            for item in positions
            if float(getattr(item, "market_value", 0) or 0) > 0
        )

        db.query(ImportedPortfolioPositionDB).filter(
            ImportedPortfolioPositionDB.user_id == user_id,
            ImportedPortfolioPositionDB.source == SOURCE_NAME,
        ).delete()

        for item in positions:
            symbol = _normalize_qmt_code(getattr(item, "stock_code", None))
            if not symbol:
                continue
            market_value = _to_float(getattr(item, "market_value", None))
            position_pct = None
            if total_market_value > 0 and market_value is not None:
                position_pct = round((market_value / total_market_value) * 100, 4)

            db.add(
                ImportedPortfolioPositionDB(
                    id=uuid4().hex,
                    user_id=user_id,
                    source=SOURCE_NAME,
                    symbol=symbol,
                    security_name=getattr(item, "instrument_name", None),
                    current_position=_to_float(getattr(item, "volume", None)),
                    available_position=_to_float(getattr(item, "can_use_volume", None)),
                    average_cost=_to_float(getattr(item, "open_price", None)),
                    market_value=market_value,
                    current_position_pct=position_pct,
                    trade_points_json=[],
                    trade_points_count=0,
                    latest_trade_at=None,
                    latest_trade_action=None,
                    last_imported_at=now,
                )
            )

        config = db.query(QmtImportConfigDB).filter(QmtImportConfigDB.user_id == user_id).first()
        if not config:
            config = QmtImportConfigDB(id=uuid4().hex, user_id=user_id, qmt_path=qmt_path, account_id=account_id)
            db.add(config)
        config.qmt_path = qmt_path
        config.account_id = account_id
        config.account_type = account_type
        config.auto_apply_scheduled = auto_apply_scheduled
        config.last_synced_at = now
        config.last_error = None

        scheduled_sync = {"created": [], "existing": [], "skipped_limit": []}
        if auto_apply_scheduled:
            ordered_symbols = [
                symbol
                for item in positions
                if (_to_float(getattr(item, "volume", None)) or 0) > 0
                for symbol in [_normalize_qmt_code(getattr(item, "stock_code", None))]
                if symbol is not None
            ]
            scheduled_sync = scheduled_service.ensure_scheduled_for_symbols(
                db=db,
                user_id=user_id,
                symbols=ordered_symbols,
            )

        db.commit()
        return get_import_state(db, user_id, scheduled_sync=scheduled_sync)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"读取 QMT 持仓失败：{exc}") from exc
    finally:
        if trader is not None and hasattr(trader, "stop"):
            try:
                trader.stop()
            except Exception as exc:
                logger.warning("[qmt] failed to stop trader cleanly: %s", exc)


def get_import_state(
    db: Session,
    user_id: str,
    scheduled_sync: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = db.query(QmtImportConfigDB).filter(QmtImportConfigDB.user_id == user_id).first()
    positions = list_imported_positions(db, user_id)
    return {
        "broker": SOURCE_NAME,
        "qmt_path": config.qmt_path if config else None,
        "account_id": config.account_id if config else None,
        "account_type": config.account_type if config else None,
        "auto_apply_scheduled": config.auto_apply_scheduled if config else False,
        "last_synced_at": config.last_synced_at.isoformat() if config and config.last_synced_at else None,
        "last_error": config.last_error if config else None,
        "summary": {
            "positions": len(positions),
        },
        "scheduled_sync": scheduled_sync or {
            "created": [],
            "existing": [],
            "skipped_limit": [],
        },
        "positions": positions,
    }


def list_imported_positions(db: Session, user_id: str) -> list[dict[str, Any]]:
    rows = (
        db.query(ImportedPortfolioPositionDB)
        .filter(
            ImportedPortfolioPositionDB.user_id == user_id,
            ImportedPortfolioPositionDB.source == SOURCE_NAME,
        )
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
    config = db.query(QmtImportConfigDB).filter(QmtImportConfigDB.user_id == user_id).first()
    if not config or not config.auto_apply_scheduled:
        return {}

    row = (
        db.query(ImportedPortfolioPositionDB)
        .filter(
            ImportedPortfolioPositionDB.user_id == user_id,
            ImportedPortfolioPositionDB.source == SOURCE_NAME,
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
        "user_notes": (
            "来源：QMT / xtquant 持仓同步\n"
            f"账户：{config.account_id}\n"
            f"QMT 路径：{config.qmt_path}"
        ),
    }
    return normalize_user_context(payload)


def clear_imported_portfolio(db: Session, user_id: str) -> None:
    db.query(ImportedPortfolioPositionDB).filter(
        ImportedPortfolioPositionDB.user_id == user_id,
        ImportedPortfolioPositionDB.source == SOURCE_NAME,
    ).delete()
    db.query(QmtImportConfigDB).filter(QmtImportConfigDB.user_id == user_id).delete()
    db.commit()


def _load_xtquant_modules():
    try:
        trader_mod = importlib.import_module("xtquant.xttrader")
        xttype_mod = importlib.import_module("xtquant.xttype")
    except ModuleNotFoundError as exc:
        raise ValueError(
            "当前环境未安装 xtquant。请先在运行后端的 Python 环境安装 QMT 的 xtquant SDK。"
        ) from exc
    return trader_mod, xttype_mod


def _validate_qmt_path(qmt_path: str) -> str:
    normalized = str(qmt_path or "").strip()
    if not normalized:
        raise ValueError("QMT 路径不能为空")
    if "\x00" in normalized:
        raise ValueError("QMT 路径格式不正确")

    pure_paths: tuple[PurePath, ...] = (PureWindowsPath(normalized), PurePosixPath(normalized))
    if not any(path.is_absolute() for path in pure_paths):
        raise ValueError("QMT 路径必须为绝对路径")
    if any(part == ".." for path in pure_paths for part in path.parts):
        raise ValueError("QMT 路径不能包含上级目录跳转")

    return str(Path(normalized))


def _normalize_qmt_code(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if "." in text:
        head, tail = text.split(".", 1)
        if head.isdigit() and tail in {"SH", "SZ", "BJ"}:
            return f"{head}.{tail}"
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None
