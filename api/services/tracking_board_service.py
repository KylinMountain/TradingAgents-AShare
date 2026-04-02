from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from api.database import ImportedPortfolioPositionDB, ReportDB
from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.dataflows.trade_calendar import cn_today_str, previous_cn_trading_day


REFRESH_INTERVAL_SECONDS = 20
logger = logging.getLogger(__name__)


def get_tracking_board(db: Session, user_id: str) -> dict[str, Any]:
    previous_trade_date = previous_cn_trading_day(cn_today_str())
    rows = _list_imported_position_rows(db, user_id)
    symbols = [row.symbol for row in rows]
    quotes = _fetch_live_quotes(symbols)
    reports = _select_reports_for_symbols(db, user_id, symbols, previous_trade_date)

    items: list[dict[str, Any]] = []
    for row in rows:
        quote = quotes.get(row.symbol, {})
        live_price = _to_float(quote.get("price"))
        current_position = _to_float(row.current_position)
        average_cost = _to_float(row.average_cost)
        live_market_value = (
            round(live_price * current_position, 2)
            if live_price is not None and current_position is not None
            else _to_float(row.market_value)
        )
        floating_pnl = (
            round((live_price - average_cost) * current_position, 2)
            if live_price is not None and average_cost is not None and current_position is not None
            else None
        )
        floating_pnl_pct = (
            round(((live_price - average_cost) / average_cost) * 100, 2)
            if live_price is not None and average_cost not in (None, 0)
            else None
        )

        items.append(
            {
                "symbol": row.symbol,
                "name": row.security_name or row.symbol,
                "current_position": _to_float(row.current_position),
                "available_position": _to_float(row.available_position),
                "average_cost": average_cost,
                "market_value": _to_float(row.market_value),
                "current_position_pct": _to_float(row.current_position_pct),
                "live_market_value": live_market_value,
                "floating_pnl": floating_pnl,
                "floating_pnl_pct": floating_pnl_pct,
                "live_price": live_price,
                "day_open": _to_float(quote.get("open")),
                "price_change": _to_float(quote.get("change")),
                "price_change_pct": _to_float(quote.get("change_pct")),
                "day_high": _to_float(quote.get("high")),
                "day_low": _to_float(quote.get("low")),
                "previous_close": _to_float(quote.get("previous_close")),
                "volume": _to_float(quote.get("volume")),
                "amount": _to_float(quote.get("amount")),
                "quote_time": quote.get("quote_time"),
                "quote_source": quote.get("source"),
                "last_imported_at": row.last_imported_at.isoformat() if row.last_imported_at else None,
                "analysis": _serialize_report_summary(reports.get(row.symbol), previous_trade_date),
            }
        )

    return {
        "previous_trade_date": previous_trade_date,
        "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
        "items": items,
    }


def _list_imported_position_rows(db: Session, user_id: str) -> list[ImportedPortfolioPositionDB]:
    """Return all imported positions for a user regardless of source."""
    return (
        db.query(ImportedPortfolioPositionDB)
        .filter(ImportedPortfolioPositionDB.user_id == user_id)
        .order_by(
            ImportedPortfolioPositionDB.market_value.desc(),
            ImportedPortfolioPositionDB.current_position.desc(),
            ImportedPortfolioPositionDB.symbol,
        )
        .all()
    )


def _select_reports_for_symbols(
    db: Session,
    user_id: str,
    symbols: list[str],
    previous_trade_date: str,
) -> dict[str, ReportDB]:
    if not symbols:
        return {}

    rows = (
        db.query(ReportDB)
        .filter(
            ReportDB.user_id == user_id,
            ReportDB.symbol.in_(symbols),
            ReportDB.status == "completed",
        )
        .order_by(ReportDB.trade_date.desc(), ReportDB.created_at.desc())
        .all()
    )

    exact_previous: dict[str, ReportDB] = {}
    latest_before_previous: dict[str, ReportDB] = {}
    latest_any: dict[str, ReportDB] = {}

    for row in rows:
        if row.symbol not in latest_any:
            latest_any[row.symbol] = row
        if row.trade_date == previous_trade_date and row.symbol not in exact_previous:
            exact_previous[row.symbol] = row
        if row.trade_date <= previous_trade_date and row.symbol not in latest_before_previous:
            latest_before_previous[row.symbol] = row

    selected: dict[str, ReportDB] = {}
    for symbol in symbols:
        report = exact_previous.get(symbol) or latest_before_previous.get(symbol) or latest_any.get(symbol)
        if report:
            selected[symbol] = report
    return selected


def _serialize_report_summary(report: ReportDB | None, previous_trade_date: str) -> dict[str, Any] | None:
    if report is None:
        return None

    return {
        "report_id": report.id,
        "trade_date": report.trade_date,
        "is_previous_trade_day": report.trade_date == previous_trade_date,
        "decision": report.decision,
        "direction": report.direction,
        "high_price": _to_float(report.target_price),
        "low_price": _to_float(report.stop_loss_price),
        "trader_advice_summary": _summarize_trader_advice(
            report.trader_investment_plan,
            fallback_text=report.final_trade_decision,
        ),
        "trader_investment_plan": report.trader_investment_plan,
        "final_trade_decision": report.final_trade_decision,
    }


def _summarize_trader_advice(text: str | None, fallback_text: str | None = None) -> str | None:
    for source in (text, fallback_text):
        if not source:
            continue

        for pattern in (
            r"最终交易建议[:：]\s*([^\n]+)",
            r"结论[:：]\s*([^\n]+)",
            r"建议动作[:：]\s*([^\n]+)",
            r"方向[:：]\s*([^\n]+)",
        ):
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                return _clip_summary(match.group(1))

        lines = [
            _clip_summary(line.strip(" -*\t"))
            for line in _strip_markdown(source).splitlines()
            if line.strip()
        ]
        for line in lines:
            if len(line) >= 6 and not re.match(r"^[一二三四五六七八九十0-9]+[、.)：:]?$", line):
                return line
    return None


def _strip_markdown(text: str) -> str:
    cleaned = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    cleaned = cleaned.replace("\r", "\n")
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*|__", "", cleaned)
    cleaned = re.sub(r"^\s*#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", cleaned)
    return cleaned


def _clip_summary(text: str | None) -> str | None:
    if text is None:
        return None
    compact = re.sub(r"\s+", " ", text).strip(" ，,;；。")
    if not compact:
        return None
    return compact[:96]


def _fetch_live_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}
    try:
        result_json = route_to_vendor("get_realtime_quotes", symbols)
        return json.loads(result_json)
    except Exception as exc:
        logger.warning("[tracking-board] realtime quote fetch failed: %s", exc)
        return {}


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except Exception:
        return None
