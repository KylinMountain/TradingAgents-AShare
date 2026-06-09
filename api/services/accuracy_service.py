"""Signal accuracy backtest service.

For each historical BUY/SELL signal, fetches actual subsequent prices
and computes return, correctness at 5/10/20 trading day horizons.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func

from api.database import ReportDB, SignalBacktestDB, get_db_ctx

logger = logging.getLogger(__name__)


def _get_trading_days_after(start_date: str, n_days: int) -> str:
    """Get the date N trading days after start_date using cached trade calendar."""
    from tradingagents.dataflows.trade_calendar import _load_cn_trade_dates
    dates, _ = _load_cn_trade_dates()
    if dates:
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        idx = 0
        for i, d in enumerate(date_strs):
            if d >= start_date:
                idx = i
                break
        target_idx = idx + n_days
        if target_idx < len(date_strs):
            return date_strs[target_idx]
        return date_strs[-1]
    # Fallback: use calendar days approximation (skip weekends)
    d = datetime.strptime(start_date, "%Y-%m-%d")
    added = 0
    while added < n_days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d.strftime("%Y-%m-%d")


def _to_tushare_code(symbol: str) -> Optional[str]:
    """Convert symbol to Tushare format (e.g. '001203.SZ'). Returns None for indices/non-stocks."""
    s = symbol.strip().upper()
    # Already in Tushare format
    if s.endswith(".SZ") or s.endswith(".SH"):
        return s
    # Bare 6-digit code
    code = s.replace(".SS", "")
    if code.isdigit() and len(code) == 6:
        if code.startswith("6"):
            return code + ".SH"
        else:
            return code + ".SZ"
    return None


def _get_price_on_date(symbol: str, date_str: str) -> Optional[float]:
    """Get closing price for a symbol on or just before date_str using Tushare."""
    try:
        import tushare as ts
        pro = ts.pro_api()
        ts_code = _to_tushare_code(symbol)
        if not ts_code:
            return None
        # Query a small window around the date
        d = datetime.strptime(date_str, "%Y-%m-%d")
        start = (d - timedelta(days=5)).strftime("%Y%m%d")
        end = d.strftime("%Y%m%d")
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=end, fields="trade_date,close")
        if df is None or df.empty:
            return None
        df = df.sort_values("trade_date", ascending=True)
        return float(df["close"].iloc[-1])
    except Exception as e:
        logger.debug(f"Failed to get price for {symbol} on {date_str}: {e}")
        return None


def backtest_signal(
    symbol: str,
    signal_date: str,
    decision: str,
    target_price: Optional[float] = None,
    stop_loss_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Run backtest for a single signal. Returns result dict."""
    if decision not in ("BUY", "SELL"):
        return {
            "signal_price": None,
            "price_5d": None, "return_5d": None, "correct_5d": None,
            "price_10d": None, "return_10d": None, "correct_10d": None,
            "price_20d": None, "return_20d": None, "correct_20d": None,
        }

    signal_price = _get_price_on_date(symbol, signal_date)
    if signal_price is None:
        logger.warning(f"No price data for {symbol} on signal date {signal_date}")
        return {
            "signal_price": None,
            "price_5d": None, "return_5d": None, "correct_5d": None,
            "price_10d": None, "return_10d": None, "correct_10d": None,
            "price_20d": None, "return_20d": None, "correct_20d": None,
        }

    result = {"signal_price": round(signal_price, 2)}
    horizons = [5, 10, 20]

    for h in horizons:
        target_date = _get_trading_days_after(signal_date, h)
        future_price = _get_price_on_date(symbol, target_date)

        if future_price is None:
            result[f"price_{h}d"] = None
            result[f"return_{h}d"] = None
            result[f"correct_{h}d"] = None
            continue

        ret = (future_price - signal_price) / signal_price
        result[f"price_{h}d"] = round(future_price, 2)
        result[f"return_{h}d"] = round(ret * 100, 2)

        if decision == "BUY":
            if target_price and future_price >= target_price:
                result[f"correct_{h}d"] = True
            else:
                result[f"correct_{h}d"] = ret > 0
        elif decision == "SELL":
            if target_price and future_price <= target_price:
                result[f"correct_{h}d"] = True
            else:
                result[f"correct_{h}d"] = ret < 0

    return result


def backfill_reports(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Run backtest on all completed reports and store results. Returns summary."""
    with get_db_ctx() as db:
        # Get completed reports with BUY/SELL decisions
        query = db.query(ReportDB).filter(
            ReportDB.status == "completed",
            ReportDB.decision.in_(["BUY", "SELL"]),
            ReportDB.result_data.isnot(None),
        )
        if user_id:
            query = query.filter(ReportDB.user_id == user_id)
        reports = query.order_by(ReportDB.trade_date.desc()).all()

        results = []
        for report in reports:
            # Skip if already backtested
            existing = db.query(SignalBacktestDB).filter(
                SignalBacktestDB.report_id == report.id
            ).first()
            if existing:
                results.append(_serialize_backtest(existing))
                continue

            bt_result = backtest_signal(
                symbol=report.symbol,
                signal_date=report.trade_date,
                decision=report.decision,
                target_price=report.target_price,
                stop_loss_price=report.stop_loss_price,
            )

            if bt_result["signal_price"] is None:
                continue

            backtest = SignalBacktestDB(
                id=str(uuid4()),
                report_id=report.id,
                user_id=report.user_id,
                symbol=report.symbol,
                signal_date=report.trade_date,
                decision=report.decision,
                confidence=report.confidence,
                signal_price=bt_result["signal_price"],
                target_price=report.target_price,
                stop_loss_price=report.stop_loss_price,
                price_5d=bt_result.get("price_5d"),
                return_5d=bt_result.get("return_5d"),
                correct_5d=bt_result.get("correct_5d"),
                price_10d=bt_result.get("price_10d"),
                return_10d=bt_result.get("return_10d"),
                correct_10d=bt_result.get("correct_10d"),
                price_20d=bt_result.get("price_20d"),
                return_20d=bt_result.get("return_20d"),
                correct_20d=bt_result.get("correct_20d"),
            )
            db.add(backtest)
            results.append(_serialize_backtest(backtest))

        db.commit()

        return {
            "total_reports": len(reports),
            "backtested": len(results),
            "results": results,
        }


def get_accuracy_summary(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get aggregated accuracy statistics."""
    with get_db_ctx() as db:
        query = db.query(SignalBacktestDB)
        if user_id:
            query = query.filter(SignalBacktestDB.user_id == user_id)
        backtests = query.all()

        if not backtests:
            return {"message": "暂无回测数据，请先运行 backfill", "total": 0}

        def _calc_stats(items, prefix):
            completed = [b for b in items if getattr(b, f"correct_{prefix}") is not None]
            if not completed:
                return {"count": 0}
            correct = sum(1 for b in completed if getattr(b, f"correct_{prefix}"))
            returns = [getattr(b, f"return_{prefix}") for b in completed if getattr(b, f"return_{prefix}") is not None]
            buy_items = [b for b in completed if b.decision == "BUY"]
            sell_items = [b for b in completed if b.decision == "SELL"]

            def _buy_correct(items):
                c = [b for b in items if getattr(b, f"correct_{prefix}") is not None]
                return sum(1 for b in c if getattr(b, f"correct_{prefix}")) if c else 0

            return {
                "count": len(completed),
                "correct": correct,
                "accuracy": round(correct / len(completed) * 100, 1),
                "avg_return": round(sum(returns) / len(returns), 2) if returns else 0,
                "max_return": round(max(returns), 2) if returns else 0,
                "min_return": round(min(returns), 2) if returns else 0,
                "buy_count": len(buy_items),
                "buy_accuracy": round(_buy_correct(buy_items) / len(buy_items) * 100, 1) if buy_items else 0,
                "sell_count": len(sell_items),
                "sell_accuracy": round(_buy_correct(sell_items) / len(sell_items) * 100, 1) if sell_items else 0,
            }

        # By confidence level
        high_conf = [b for b in backtests if b.confidence and b.confidence >= 70]
        med_conf = [b for b in backtests if b.confidence and 40 <= b.confidence < 70]
        low_conf = [b for b in backtests if b.confidence and b.confidence < 40]

        # By symbol
        symbols = {}
        for b in backtests:
            if b.symbol not in symbols:
                symbols[b.symbol] = []
            symbols[b.symbol].append(b)

        symbol_stats = {}
        for sym, items in symbols.items():
            name = sym.replace(".SZ", "").replace(".SH", "")
            s20 = _calc_stats(items, "20d")
            symbol_stats[name] = {"count": len(items), "accuracy_20d": s20.get("accuracy", 0), "avg_return_20d": s20.get("avg_return", 0)}

        return {
            "total": len(backtests),
            "horizon_5d": _calc_stats(backtests, "5d"),
            "horizon_10d": _calc_stats(backtests, "10d"),
            "horizon_20d": _calc_stats(backtests, "20d"),
            "by_confidence": {
                "high": _calc_stats(high_conf, "10d"),
                "medium": _calc_stats(med_conf, "10d"),
                "low": _calc_stats(low_conf, "10d"),
            },
            "by_symbol": symbol_stats,
        }


def get_accuracy_details(
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Get per-signal accuracy details with pagination."""
    with get_db_ctx() as db:
        query = db.query(SignalBacktestDB)
        if user_id:
            query = query.filter(SignalBacktestDB.user_id == user_id)
        total = query.count()
        backtests = query.order_by(SignalBacktestDB.signal_date.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [_serialize_backtest(b) for b in backtests],
        }


def _serialize_backtest(b: SignalBacktestDB) -> Dict[str, Any]:
    return {
        "id": b.id,
        "report_id": b.report_id,
        "symbol": b.symbol.replace(".SZ", "").replace(".SH", ""),
        "signal_date": b.signal_date,
        "decision": b.decision,
        "confidence": b.confidence,
        "signal_price": b.signal_price,
        "target_price": b.target_price,
        "stop_loss_price": b.stop_loss_price,
        "price_5d": b.price_5d,
        "return_5d": b.return_5d,
        "correct_5d": b.correct_5d,
        "price_10d": b.price_10d,
        "return_10d": b.return_10d,
        "correct_10d": b.correct_10d,
        "price_20d": b.price_20d,
        "return_20d": b.return_20d,
        "correct_20d": b.correct_20d,
    }
