from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.database import ImportedPortfolioPositionDB, QmtImportConfigDB, ReportDB
from api.services.qmt_import_service import SOURCE_NAME
from tradingagents.dataflows.trade_calendar import cn_today_str, previous_cn_trading_day


REFRESH_INTERVAL_SECONDS = 20


def get_tracking_board(db: Session, user_id: str) -> dict[str, Any]:
    config = db.query(QmtImportConfigDB).filter(QmtImportConfigDB.user_id == user_id).first()
    previous_trade_date = previous_cn_trading_day(cn_today_str())
    rows = _list_qmt_position_rows(db, user_id)
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
            ImportedPortfolioPositionDB.market_value.desc().nullslast(),
            ImportedPortfolioPositionDB.current_position.desc().nullslast(),
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

    quotes = _fetch_qmt_quotes(symbols)
    missing = [symbol for symbol in symbols if symbol not in quotes]
    if not missing:
        return quotes

    fallback_quotes = _fetch_em_batch_quotes(missing)
    quotes.update(fallback_quotes)
    missing = [symbol for symbol in symbols if symbol not in quotes]
    for symbol in missing:
        quote = _fetch_xq_quote(symbol)
        if quote:
            quotes[symbol] = quote
    return quotes


def _fetch_qmt_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    try:
        import xtquant.xtdata as xtdata  # type: ignore
    except Exception:
        return {}

    normalized_symbols = [symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()]
    if not normalized_symbols:
        return {}

    try:
        raw = xtdata.get_full_tick(normalized_symbols)
    except Exception:
        return {}

    if not isinstance(raw, dict):
        return {}

    quotes: dict[str, dict[str, Any]] = {}
    for symbol in normalized_symbols:
        tick = raw.get(symbol)
        if not isinstance(tick, dict):
            continue

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
            try:
                quote_time = datetime.fromtimestamp(float(tick["time"]) / 1000, tz=timezone.utc).isoformat()
            except Exception:
                quote_time = None

        quotes[symbol] = {
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

    return quotes


def _fetch_em_batch_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    try:
        import akshare as ak  # type: ignore

        df = ak.stock_zh_a_spot_em()
    except Exception:
        return {}

    if df is None or df.empty:
        return {}

    symbol_by_code = {_extract_code(symbol): symbol for symbol in symbols}
    if "代码" not in df.columns:
        return {}

    df = df.copy()
    df["代码"] = df["代码"].astype(str).str.zfill(6)
    filtered = df[df["代码"].isin(symbol_by_code.keys())]
    if filtered.empty:
        return {}

    now_iso = datetime.now(timezone.utc).isoformat()
    quotes: dict[str, dict[str, Any]] = {}
    for _, row in filtered.iterrows():
        symbol = symbol_by_code.get(str(row.get("代码", "")).zfill(6))
        if not symbol:
            continue
        quotes[symbol] = {
            "price": _to_float(row.get("最新价")),
            "open": _to_float(row.get("今开")),
            "change": _to_float(row.get("涨跌额")),
            "change_pct": _to_float(row.get("涨跌幅")),
            "high": _to_float(row.get("最高")),
            "low": _to_float(row.get("最低")),
            "previous_close": _to_float(row.get("昨收")),
            "quote_time": now_iso,
            "source": "akshare_em_spot",
        }
    return quotes


def _fetch_xq_quote(symbol: str) -> dict[str, Any] | None:
    try:
        import akshare as ak  # type: ignore

        spot = ak.stock_individual_spot_xq(symbol=_to_xq_symbol(symbol))
    except Exception:
        return None

    if spot is None or getattr(spot, "empty", True):
        return None
    if not {"item", "value"}.issubset(set(spot.columns)):
        return None

    kv = dict(zip(spot["item"].astype(str), spot["value"]))
    quote_time = kv.get("时间")
    if quote_time:
        quote_time = str(quote_time)

    return {
        "price": _to_float(kv.get("现价")),
        "open": _to_float(kv.get("今开")),
        "change": _to_float(kv.get("涨跌")),
        "change_pct": _to_float(kv.get("涨幅")),
        "high": _to_float(kv.get("最高")),
        "low": _to_float(kv.get("最低")),
        "previous_close": _to_float(kv.get("昨收")),
        "quote_time": quote_time,
        "source": "akshare_xq_spot",
    }


def _extract_code(symbol: str) -> str:
    return str(symbol or "").split(".", 1)[0].strip().zfill(6)


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
