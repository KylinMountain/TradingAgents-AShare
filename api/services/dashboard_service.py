from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests
from sqlalchemy.orm import Session

from api.database import ImportedPortfolioPositionDB, QmtImportConfigDB, ReportDB
from api.services.qmt_import_service import SOURCE_NAME
from tradingagents.dataflows.trade_calendar import cn_today_str, previous_cn_trading_day


REFRESH_INTERVAL_SECONDS = 20
QUOTE_REQUEST_TIMEOUT_SECONDS = max(0.5, float(os.getenv("TA_TRACKING_QUOTE_TIMEOUT_SECONDS", "2.5")))
ENABLE_XQ_QUOTE_FALLBACK = os.getenv("TA_TRACKING_ENABLE_XQ_FALLBACK", "").strip().lower() in ("1", "true", "yes", "on")
logger = logging.getLogger(__name__)


def get_tracking_board(db: Session, user_id: str) -> dict[str, Any]:
    config = db.query(QmtImportConfigDB).filter(QmtImportConfigDB.user_id == user_id).first()
    previous_trade_date = previous_cn_trading_day(cn_today_str())
    rows = _list_qmt_position_rows(db, user_id)
    symbols = [row.symbol for row in rows]
    quotes = _fetch_live_quotes(symbols, prefer_qmt_only=bool(config and config.qmt_path))
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
        "broker": SOURCE_NAME,
        "qmt_path": config.qmt_path if config else None,
        "account_id": config.account_id if config else None,
        "account_type": config.account_type if config else None,
        "last_synced_at": config.last_synced_at.isoformat() if config and config.last_synced_at else None,
        "previous_trade_date": previous_trade_date,
        "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
        "items": items,
    }


def _list_qmt_position_rows(db: Session, user_id: str) -> list[ImportedPortfolioPositionDB]:
    return (
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


def _fetch_live_quotes(
    symbols: list[str],
    *,
    prefer_qmt_only: bool = False,
) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}

    quotes = _fetch_qmt_quotes(symbols)
    missing = [symbol for symbol in symbols if symbol not in quotes]
    if not missing or prefer_qmt_only:
        return quotes

    fallback_quotes = _fetch_em_batch_quotes(missing)
    quotes.update(fallback_quotes)
    missing = [symbol for symbol in symbols if symbol not in quotes]
    if ENABLE_XQ_QUOTE_FALLBACK:
        for symbol in missing:
            quote = _fetch_xq_quote(symbol)
            if quote:
                quotes[symbol] = quote
    return quotes


def _fetch_qmt_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    try:
        import xtquant.xtdata as xtdata  # type: ignore
    except Exception as exc:
        logger.warning("[tracking-board] xtdata import failed: %s", exc)
        return {}

    normalized_symbols = [symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()]
    if not normalized_symbols:
        return {}

    try:
        raw = xtdata.get_full_tick(normalized_symbols)
    except Exception as exc:
        logger.warning("[tracking-board] xtdata quote fetch failed for %s: %s", normalized_symbols, exc)
        raw = {}

    quotes: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        for symbol in normalized_symbols:
            tick = raw.get(symbol)
            if not isinstance(tick, dict):
                continue
            quote = _build_qmt_quote_from_mapping(tick)
            if quote:
                quotes[symbol] = quote

    if quotes:
        return quotes

    subscription_ids: list[int] = []
    try:
        for symbol in normalized_symbols:
            try:
                subscription_id = xtdata.subscribe_quote(symbol, period="tick", count=1)
                if subscription_id is not None:
                    subscription_ids.append(int(subscription_id))
            except Exception as exc:
                logger.warning("[tracking-board] xtdata subscribe_quote failed for %s: %s", symbol, exc)
        if subscription_ids:
            time.sleep(0.35)

        try:
            raw_frames = xtdata.get_market_data_ex(
                field_list=["time", "lastPrice", "open", "high", "low", "lastClose", "amount", "volume"],
                stock_list=normalized_symbols,
                period="tick",
                count=1,
            )
        except Exception as exc:
            logger.warning("[tracking-board] xtdata tick frame fetch failed for %s: %s", normalized_symbols, exc)
            return quotes

        if not isinstance(raw_frames, dict):
            return quotes

        for symbol in normalized_symbols:
            frame = raw_frames.get(symbol)
            quote = _build_qmt_quote_from_frame(frame)
            if quote:
                quotes[symbol] = quote
    finally:
        unsubscribe = getattr(xtdata, "unsubscribe_quote", None)
        if callable(unsubscribe):
            for subscription_id in subscription_ids:
                try:
                    unsubscribe(subscription_id)
                except Exception:
                    pass

    return quotes


def _build_qmt_quote_from_mapping(tick: dict[str, Any]) -> dict[str, Any] | None:
    last_price = _to_float(tick.get("lastPrice"))
    previous_close = _to_float(tick.get("lastClose") or tick.get("lastSettlementPrice"))
    change = _to_float(tick.get("change"))
    if change is None and last_price is not None and previous_close is not None:
        change = round(last_price - previous_close, 4)

    change_pct = _to_float(tick.get("changePercent") or tick.get("changePct"))
    if change_pct is None and change is not None and previous_close not in (None, 0):
        change_pct = round((change / previous_close) * 100, 4)

    quote_time = tick.get("timetag")
    if not quote_time and tick.get("time") is not None:
        quote_time = _to_iso_datetime(tick.get("time"))

    if all(
        value is None for value in (
            last_price,
            _to_float(tick.get("open")),
            _to_float(tick.get("high")),
            _to_float(tick.get("low")),
        )
    ):
        return None

    return {
        "price": last_price,
        "open": _to_float(tick.get("open")),
        "change": change,
        "change_pct": change_pct,
        "high": _to_float(tick.get("high")),
        "low": _to_float(tick.get("low")),
        "previous_close": previous_close,
        "volume": _to_float(tick.get("volume") or tick.get("pvolume")),
        "amount": _to_float(tick.get("amount")),
        "quote_time": str(quote_time) if quote_time else None,
        "source": "qmt_xtdata",
    }


def _build_qmt_quote_from_frame(frame: Any) -> dict[str, Any] | None:
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        row = frame.iloc[-1]
    except Exception:
        return None

    tick = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    return _build_qmt_quote_from_mapping(tick)


def _to_iso_datetime(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        timestamp = float(value)
        if timestamp > 1e12:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except Exception:
        return None


def _fetch_em_batch_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    sina_symbols = [_to_sina_symbol(symbol) for symbol in symbols if _to_sina_symbol(symbol)]
    if not sina_symbols:
        return {}
    try:
        response = requests.get(
            "https://hq.sinajs.cn/list=" + ",".join(sina_symbols),
            timeout=QUOTE_REQUEST_TIMEOUT_SECONDS,
            headers={
                "Referer": "https://finance.sina.com.cn/",
                "User-Agent": "Mozilla/5.0",
            },
        )
        response.raise_for_status()
        response.encoding = "gbk"
    except Exception as exc:
        logger.warning("[tracking-board] Batch quote fetch failed for %s: %s", symbols, exc)
        return {}

    symbol_by_sina = {
        _to_sina_symbol(symbol): str(symbol or "").strip().upper()
        for symbol in symbols
        if _to_sina_symbol(symbol)
    }
    quotes: dict[str, dict[str, Any]] = {}
    for line in response.text.splitlines():
        symbol, quote = _parse_sina_quote_line(line)
        if not symbol or not quote:
            continue
        target_symbol = symbol_by_sina.get(symbol)
        if not target_symbol:
            continue
        quotes[target_symbol] = quote
    return quotes


def _fetch_xq_quote(symbol: str) -> dict[str, Any] | None:
    return _fetch_em_batch_quotes([symbol]).get(str(symbol or "").strip().upper())


def _parse_sina_quote_line(line: str) -> tuple[str | None, dict[str, Any] | None]:
    match = re.match(r'^var hq_str_(?P<symbol>[^=]+)="(?P<body>.*)";$', str(line or "").strip())
    if not match:
        return None, None

    raw_symbol = match.group("symbol").strip().lower()
    fields = match.group("body").split(",")
    if len(fields) < 10 or not any(field.strip() for field in fields):
        return raw_symbol, None

    date_part = fields[30].strip() if len(fields) > 30 else ""
    time_part = fields[31].strip() if len(fields) > 31 else ""
    quote_time = None
    if date_part and time_part:
        try:
            quote_time = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            ).isoformat()
        except Exception:
            quote_time = None

    price = _to_float(fields[3] if len(fields) > 3 else None)
    open_price = _to_float(fields[1] if len(fields) > 1 else None)
    previous_close = _to_float(fields[2] if len(fields) > 2 else None)
    high = _to_float(fields[4] if len(fields) > 4 else None)
    low = _to_float(fields[5] if len(fields) > 5 else None)
    volume = _to_float(fields[8] if len(fields) > 8 else None)
    amount = _to_float(fields[9] if len(fields) > 9 else None)
    if all(value is None for value in (price, open_price, previous_close, high, low)):
        return raw_symbol, None

    change = (
        round(price - previous_close, 4)
        if price is not None and previous_close is not None
        else None
    )
    change_pct = (
        round((change / previous_close) * 100, 4)
        if change is not None and previous_close not in (None, 0)
        else None
    )

    return raw_symbol, {
        "price": price,
        "open": open_price,
        "change": change,
        "change_pct": change_pct,
        "high": high,
        "low": low,
        "previous_close": previous_close,
        "volume": volume,
        "amount": amount,
        "quote_time": quote_time,
        "source": "sina_hq",
    }


def _extract_code(symbol: str) -> str:
    return str(symbol or "").split(".", 1)[0].strip().zfill(6)


def _to_sina_symbol(symbol: str) -> str | None:
    code = _extract_code(symbol)
    upper_symbol = str(symbol or "").upper()
    if not code:
        return None
    if upper_symbol.endswith(".BJ"):
        return f"bj{code}"
    if code.startswith(("5", "6", "9")):
        return f"sh{code}"
    return f"sz{code}"


def _to_xq_symbol(symbol: str) -> str:
    code = _extract_code(symbol)
    upper_symbol = str(symbol or "").upper()
    if upper_symbol.endswith(".BJ"):
        return f"BJ{code}"
    if code.startswith(("5", "6", "9")):
        return f"SH{code}"
    return f"SZ{code}"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except Exception:
        return None
