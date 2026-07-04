"""Signal accuracy backtest service.

For each historical BUY/SELL signal, fetches actual subsequent prices
and computes return, correctness, max drawdown, and benchmark comparison
at 5/10/20 trading day horizons.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from api.database import ReportDB, SignalBacktestDB, get_db_ctx

logger = logging.getLogger(__name__)

# ── Migration ────────────────────────────────────────────────────────────────


def _ensure_backtest_columns():
    """Add new columns to signal_backtests if they don't exist (zero-downtime migration)."""
    try:
        with get_db_ctx() as db:
            conn = db.connection()
            result = conn.execute(text("PRAGMA table_info(signal_backtests)"))
            existing_cols = {row[1] for row in result}
            needed = {
                "entry_date": "VARCHAR(10)",
                "max_drawdown_5d": "FLOAT",
                "max_drawdown_10d": "FLOAT",
                "max_drawdown_20d": "FLOAT",
                "benchmark_return_5d": "FLOAT",
                "benchmark_return_10d": "FLOAT",
                "benchmark_return_20d": "FLOAT",
            }
            for col, col_type in needed.items():
                if col not in existing_cols:
                    conn.execute(text(f"ALTER TABLE signal_backtests ADD COLUMN {col} {col_type}"))
            db.commit()
    except Exception as e:
        logger.debug(f"Backtest migration skipped (table may not exist yet): {e}")


_ensure_backtest_columns()

# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_trading_days_after(start_date: str, n_days: int) -> str:
    """Get the date N trading days after start_date using cached trade calendar."""
    from tradingagents.dataflows.trade_calendar import _load_cn_trade_dates, is_cn_trading_day

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

    # Fallback: use is_cn_trading_day for holiday-aware skipping
    logger.warning("Trade calendar unavailable, using degraded fallback for %s +%d", start_date, n_days)
    d = datetime.strptime(start_date, "%Y-%m-%d")
    added = 0
    while added < n_days:
        d += timedelta(days=1)
        if is_cn_trading_day(d.strftime("%Y-%m-%d")):
            added += 1
    return d.strftime("%Y-%m-%d")


def _to_tushare_code(symbol: str) -> Optional[str]:
    """Convert symbol to Tushare format (e.g. '001203.SZ'). Returns None for indices/non-stocks."""
    s = symbol.strip().upper()
    if s.endswith(".SZ") or s.endswith(".SH"):
        return s
    code = s.replace(".SS", "")
    if code.isdigit() and len(code) == 6:
        if code.startswith("6"):
            return code + ".SH"
        else:
            return code + ".SZ"
    return None


def _get_price_on_date(symbol: str, date_str: str) -> Optional[float]:
    """Get closing price for a symbol on or just before date_str using Tushare.

    Lookback window extended to 15 calendar days to cover long holidays.
    """
    try:
        import tushare as ts
        pro = ts.pro_api()
        ts_code = _to_tushare_code(symbol)
        if not ts_code:
            return None
        d = datetime.strptime(date_str, "%Y-%m-%d")
        start = (d - timedelta(days=15)).strftime("%Y%m%d")
        end = d.strftime("%Y%m%d")
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=end, fields="trade_date,close")
        if df is None or df.empty:
            return None
        df = df.sort_values("trade_date", ascending=True)
        return float(df["close"].iloc[-1])
    except Exception as e:
        logger.debug(f"Failed to get price for {symbol} on {date_str}: {e}")
        return None


def _get_daily_prices(symbol: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Get daily OHLC prices between two dates (inclusive). One Tushare call."""
    try:
        import tushare as ts
        pro = ts.pro_api()
        ts_code = _to_tushare_code(symbol)
        if not ts_code:
            return []
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=end,
                       fields="trade_date,open,high,low,close")
        if df is None or df.empty:
            return []
        df = df.sort_values("trade_date", ascending=True)
        return [
            {
                "date": row["trade_date"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
            for _, row in df.iterrows()
        ]
    except Exception as e:
        logger.debug(f"Failed to get daily prices for {symbol}: {e}")
        return []


def _get_index_price_on_date(index_code: str, date_str: str) -> Optional[float]:
    """Get index closing price via Tushare index_daily (for benchmark)."""
    try:
        import tushare as ts
        pro = ts.pro_api()
        d = datetime.strptime(date_str, "%Y-%m-%d")
        start = (d - timedelta(days=10)).strftime("%Y%m%d")
        end = d.strftime("%Y%m%d")
        df = pro.index_daily(ts_code=index_code, start_date=start, end_date=end, fields="trade_date,close")
        if df is None or df.empty:
            return None
        df = df.sort_values("trade_date", ascending=True)
        return float(df["close"].iloc[-1])
    except Exception as e:
        logger.debug(f"Failed to get index price for {index_code} on {date_str}: {e}")
        return None


def _get_benchmark_return(start_date: str, end_date: str) -> Optional[float]:
    """Get 上证指数 (000001.SH) return between two dates."""
    start_price = _get_index_price_on_date("000001.SH", start_date)
    end_price = _get_index_price_on_date("000001.SH", end_date)
    if start_price and end_price and start_price > 0:
        return round((end_price - start_price) / start_price * 100, 2)
    return None


def _empty_result() -> Dict[str, Any]:
    return {
        "signal_price": None,
        "entry_date": None,
        "price_5d": None, "return_5d": None, "correct_5d": None,
        "max_drawdown_5d": None, "benchmark_return_5d": None,
        "price_10d": None, "return_10d": None, "correct_10d": None,
        "max_drawdown_10d": None, "benchmark_return_10d": None,
        "price_20d": None, "return_20d": None, "correct_20d": None,
        "max_drawdown_20d": None, "benchmark_return_20d": None,
    }

# ── Core backtest ────────────────────────────────────────────────────────────


def backtest_signal(
    symbol: str,
    signal_date: str,
    decision: str,
    target_price: Optional[float] = None,
    stop_loss_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Run backtest for a single signal against actual market data.

    Key design:
    - Entry at next-trading-day close (eliminates look-ahead bias)
    - Max drawdown computed from daily low/high between entry and horizon
    - Stop-loss checked against intra-period extremes
    - Target price validated for directional sanity
    - Delisted / no-data treated as incorrect (survivorship bias fix)
    - Benchmark = 上证指数 over the same period
    """
    if decision not in ("BUY", "SELL"):
        return _empty_result()

    # Entry = next trading day after signal (no look-ahead)
    entry_date = _get_trading_days_after(signal_date, 1)
    signal_price = _get_price_on_date(symbol, entry_date)
    if signal_price is None:
        logger.warning("No entry price for %s on %s, signal on %s", symbol, entry_date, signal_date)
        return _empty_result()

    result: Dict[str, Any] = {
        "signal_price": round(signal_price, 2),
        "entry_date": entry_date,
    }

    # One Tushare call for all daily prices from entry to farthest horizon
    far_date = _get_trading_days_after(signal_date, 20)
    daily_prices = _get_daily_prices(symbol, entry_date, far_date)

    # Target price direction validation
    target_valid = False
    if target_price and target_price > 0 and signal_price > 0:
        if decision == "BUY" and target_price > signal_price:
            target_valid = True
        elif decision == "SELL" and target_price < signal_price:
            target_valid = True

    horizons = [5, 10, 20]

    # Benchmark: cache index start price (same entry_date for all horizons)
    index_start_price = _get_index_price_on_date("000001.SH", entry_date)

    for h in horizons:
        target_date = _get_trading_days_after(signal_date, h)
        future_price = _get_price_on_date(symbol, target_date)

        if future_price is None:
            # Target date not yet reached → leave as None (incomplete, exclude from stats)
            if target_date > date.today().isoformat():
                continue
            # Delisted / truly unavailable → mark as failed
            result[f"price_{h}d"] = None
            result[f"return_{h}d"] = -100.0
            result[f"correct_{h}d"] = False
            result[f"max_drawdown_{h}d"] = -100.0
            result[f"benchmark_return_{h}d"] = None
            continue

        ret = (future_price - signal_price) / signal_price
        result[f"price_{h}d"] = round(future_price, 2)
        result[f"return_{h}d"] = round(ret * 100, 2)

        # Max drawdown & stop-loss check from intra-period extremes
        target_date_fmt = target_date.replace("-", "")
        period_lows = [p["low"] for p in daily_prices if p["date"] <= target_date_fmt]
        period_highs = [p["high"] for p in daily_prices if p["date"] <= target_date_fmt]

        stopped_out = False
        if decision == "BUY":
            if period_lows:
                period_extreme = min(period_lows)
                max_dd = round(
                    (period_extreme - signal_price) / signal_price * 100, 2
                ) if period_extreme < signal_price else 0.0
                if stop_loss_price and period_extreme <= stop_loss_price:
                    stopped_out = True
            else:
                max_dd = None  # daily prices unavailable
        else:  # SELL
            if period_highs:
                period_extreme = max(period_highs)
                max_dd = round(
                    (signal_price - period_extreme) / signal_price * 100, 2
                ) if period_extreme > signal_price else 0.0
                if stop_loss_price and period_extreme >= stop_loss_price:
                    stopped_out = True
            else:
                max_dd = None  # daily prices unavailable

        result[f"max_drawdown_{h}d"] = max_dd

        # Benchmark return over same period (start price cached)
        bench_end_price = _get_index_price_on_date("000001.SH", target_date)
        if index_start_price and bench_end_price and index_start_price > 0:
            result[f"benchmark_return_{h}d"] = round((bench_end_price - index_start_price) / index_start_price * 100, 2)
        else:
            result[f"benchmark_return_{h}d"] = None

        # Correctness determination
        if stopped_out:
            result[f"correct_{h}d"] = False
        elif decision == "BUY":
            if target_valid and future_price >= target_price:
                result[f"correct_{h}d"] = True
            else:
                result[f"correct_{h}d"] = ret > 0
        elif decision == "SELL":
            if target_valid and future_price <= target_price:
                result[f"correct_{h}d"] = True
            else:
                result[f"correct_{h}d"] = ret < 0

    return result

# ── Backfill ─────────────────────────────────────────────────────────────────


def backfill_reports(user_id: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
    """Run backtest on all completed reports and store results. Returns summary.
    Set force=True to recompute ALL backtests (e.g., after backtest logic update)."""
    with get_db_ctx() as db:
        # Clean up orphaned backtest records (reports already deleted)
        orphan_query = db.query(SignalBacktestDB).filter(
            ~SignalBacktestDB.report_id.in_(db.query(ReportDB.id).subquery())
        )
        if user_id:
            orphan_query = orphan_query.filter(SignalBacktestDB.user_id == user_id)
        orphan_count = orphan_query.delete(synchronize_session='fetch')
        if orphan_count > 0:
            db.commit()
            logger.info(f"Cleaned up {orphan_count} orphaned backtest records")

        query = db.query(ReportDB).filter(
            ReportDB.status == "completed",
            ReportDB.decision.in_(["BUY", "SELL"]),
            ReportDB.result_data.isnot(None),
        )
        if user_id:
            query = query.filter(ReportDB.user_id == user_id)
        reports = query.order_by(ReportDB.trade_date.desc()).all()

        results: List[Dict] = []
        incomplete_count = 0  # signals too recent for 20d horizon

        for report in reports:
            existing = db.query(SignalBacktestDB).filter(
                SignalBacktestDB.report_id == report.id
            ).first()
            if not force and existing and existing.correct_5d is not None and existing.correct_10d is not None and existing.correct_20d is not None:
                results.append(_serialize_backtest(existing))
                continue
            if existing:
                db.delete(existing)
                db.flush()

            bt_result = backtest_signal(
                symbol=report.symbol,
                signal_date=report.trade_date,
                decision=report.decision,
                target_price=report.target_price,
                stop_loss_price=report.stop_loss_price,
            )

            if bt_result["signal_price"] is None:
                continue

            # Count signals missing the 20d horizon
            if bt_result.get("correct_20d") is None and bt_result.get("correct_5d") is not None:
                incomplete_count += 1

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
                entry_date=bt_result.get("entry_date"),
                max_drawdown_5d=bt_result.get("max_drawdown_5d"),
                max_drawdown_10d=bt_result.get("max_drawdown_10d"),
                max_drawdown_20d=bt_result.get("max_drawdown_20d"),
                benchmark_return_5d=bt_result.get("benchmark_return_5d"),
                benchmark_return_10d=bt_result.get("benchmark_return_10d"),
                benchmark_return_20d=bt_result.get("benchmark_return_20d"),
            )
            db.add(backtest)
            results.append(_serialize_backtest(backtest))

        db.commit()

        return {
            "total_reports": len(reports),
            "backtested": len(results),
            "incomplete_20d": incomplete_count,
            "results": results,
        }

# ── Summary / aggregation ───────────────────────────────────────────────────


def _get_valid_backtest_query(db: Session, user_id: Optional[str] = None):
    """Return query for backtests whose source report still exists (exclude orphans)."""
    valid_report_ids = db.query(ReportDB.id).subquery()
    query = db.query(SignalBacktestDB).filter(
        SignalBacktestDB.report_id.in_(valid_report_ids)
    )
    if user_id:
        query = query.filter(SignalBacktestDB.user_id == user_id)
    return query


def get_accuracy_summary(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get aggregated accuracy statistics with win/loss ratio, drawdown, benchmark."""
    with get_db_ctx() as db:
        backtests: List[SignalBacktestDB] = _get_valid_backtest_query(db, user_id).all()

        if not backtests:
            return {
                "message": "暂无回测数据，请先运行 backfill",
                "total": 0,
                "sample_warning": None,
            }

        def _calc_stats(items: List[SignalBacktestDB], prefix: str) -> Dict[str, Any]:
            completed = [b for b in items if getattr(b, f"correct_{prefix}") is not None]
            if not completed:
                return {"count": 0}

            correct = sum(1 for b in completed if getattr(b, f"correct_{prefix}"))
            returns = [getattr(b, f"return_{prefix}") for b in completed
                       if getattr(b, f"return_{prefix}") is not None]
            drawdowns = [getattr(b, f"max_drawdown_{prefix}") for b in completed
                         if getattr(b, f"max_drawdown_{prefix}") is not None]
            benchmarks = [getattr(b, f"benchmark_return_{prefix}") for b in completed
                          if getattr(b, f"benchmark_return_{prefix}") is not None]

            buy_items = [b for b in completed if b.decision == "BUY"]
            sell_items = [b for b in completed if b.decision == "SELL"]

            def _dir_correct(items: List) -> int:
                c = [b for b in items if getattr(b, f"correct_{prefix}") is not None]
                return sum(1 for b in c if getattr(b, f"correct_{prefix}")) if c else 0

            # Win/loss ratio & expected value
            wins = [r for r in returns if r > 0]
            losses = [r for r in returns if r <= 0]
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            win_loss_ratio = round(avg_win / abs(avg_loss), 2) if avg_loss != 0 else (999 if avg_win > 0 else 0)
            win_rate = len(wins) / len(returns) if returns else 0
            loss_rate = len(losses) / len(returns) if returns else 0
            expected_value = round(win_rate * avg_win + loss_rate * avg_loss, 2)

            # Benchmark excess — pair by item to avoid misalignment
            excess_returns = []
            for b in completed:
                ret = getattr(b, f"return_{prefix}")
                bench = getattr(b, f"benchmark_return_{prefix}")
                if ret is not None and bench is not None:
                    excess_returns.append(ret - bench)
            avg_excess = round(sum(excess_returns) / len(excess_returns), 2) if excess_returns else None
            beat_benchmark = sum(1 for e in excess_returns if e > 0) if excess_returns else 0
            beat_benchmark_pct = round(beat_benchmark / len(excess_returns) * 100, 1) if excess_returns else None

            stats = {
                "count": len(completed),
                "correct": correct,
                "accuracy": round(correct / len(completed) * 100, 1),
                "avg_return": round(sum(returns) / len(returns), 2) if returns else 0,
                "max_return": round(max(returns), 2) if returns else 0,
                "min_return": round(min(returns), 2) if returns else 0,
                "avg_max_drawdown": round(sum(drawdowns) / len(drawdowns), 2) if drawdowns else 0,
                "avg_benchmark_return": round(sum(benchmarks) / len(benchmarks), 2) if benchmarks else None,
                "avg_excess_return": avg_excess,
                "beat_benchmark_pct": beat_benchmark_pct,
                "win_loss_ratio": win_loss_ratio,
                "expected_value": expected_value,
                "buy_count": len(buy_items),
                "buy_accuracy": round(_dir_correct(buy_items) / len(buy_items) * 100, 1) if buy_items else 0,
                "sell_count": len(sell_items),
                "sell_accuracy": round(_dir_correct(sell_items) / len(sell_items) * 100, 1) if sell_items else 0,
            }
            return stats

        # Sample size warning
        total = len(backtests)
        if total < 10:
            sample_warning = "样本量不足（<10条），统计结果仅供参考"
        elif total < 30:
            sample_warning = "样本量偏少（<30条），统计误差较大"
        else:
            sample_warning = None

        # Incomplete horizon count
        incomplete_20d = sum(
            1 for b in backtests
            if getattr(b, "correct_20d") is None and getattr(b, "correct_5d") is not None
        )

        # By confidence level
        high_conf = [b for b in backtests if b.confidence is not None and b.confidence >= 70]
        med_conf = [b for b in backtests if b.confidence is not None and 40 <= b.confidence < 70]
        low_conf = [b for b in backtests if b.confidence is not None and b.confidence < 40]

        # By symbol
        symbols: Dict[str, List[SignalBacktestDB]] = {}
        for b in backtests:
            symbols.setdefault(b.symbol, []).append(b)

        symbol_stats = {}
        for sym, items in symbols.items():
            name = sym.replace(".SZ", "").replace(".SH", "")
            s20 = _calc_stats(items, "20d")
            symbol_stats[name] = {
                "count": len(items),
                "accuracy_20d": s20.get("accuracy", 0),
                "avg_return_20d": s20.get("avg_return", 0),
                "avg_max_drawdown_20d": s20.get("avg_max_drawdown", 0),
                "win_loss_ratio_20d": s20.get("win_loss_ratio", 0),
            }

        return {
            "total": total,
            "sample_warning": sample_warning,
            "incomplete_20d_count": incomplete_20d,
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

# ── Details ──────────────────────────────────────────────────────────────────


def get_accuracy_details(
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Get per-signal accuracy details with pagination."""
    with get_db_ctx() as db:
        query = _get_valid_backtest_query(db, user_id)
        total = query.count()
        items = query.order_by(SignalBacktestDB.signal_date.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": [_serialize_backtest(b) for b in items],
        }


def _serialize_backtest(b: SignalBacktestDB) -> Dict[str, Any]:
    return {
        "id": b.id,
        "report_id": b.report_id,
        "symbol": b.symbol.replace(".SZ", "").replace(".SH", ""),
        "signal_date": b.signal_date,
        "entry_date": b.entry_date,
        "decision": b.decision,
        "confidence": b.confidence,
        "signal_price": b.signal_price,
        "target_price": b.target_price,
        "stop_loss_price": b.stop_loss_price,
        "price_5d": b.price_5d,
        "return_5d": b.return_5d,
        "correct_5d": b.correct_5d,
        "max_drawdown_5d": b.max_drawdown_5d,
        "benchmark_return_5d": b.benchmark_return_5d,
        "price_10d": b.price_10d,
        "return_10d": b.return_10d,
        "correct_10d": b.correct_10d,
        "max_drawdown_10d": b.max_drawdown_10d,
        "benchmark_return_10d": b.benchmark_return_10d,
        "price_20d": b.price_20d,
        "return_20d": b.return_20d,
        "correct_20d": b.correct_20d,
        "max_drawdown_20d": b.max_drawdown_20d,
        "benchmark_return_20d": b.benchmark_return_20d,
    }
