"""
Backtest service — runs historical analysis for a symbol across a date range
and compares each decision against subsequent price performance.

Design: completely non-invasive. Reuses existing TradingAgentsGraph.propagate()
without touching any existing code.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

# ──────────────────────────────────────────────────────────────────────────────
# In-memory store (no additional DB table — results stored as JSON in the job)
# ──────────────────────────────────────────────────────────────────────────────
_backtest_jobs: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set(job_id: str, **kwargs: Any) -> None:
    with _lock:
        if job_id not in _backtest_jobs:
            _backtest_jobs[job_id] = {}
        _backtest_jobs[job_id].update(kwargs)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _backtest_jobs.get(job_id)


def list_jobs() -> List[Dict[str, Any]]:
    with _lock:
        return sorted(_backtest_jobs.values(), key=lambda j: j.get("created_at", ""), reverse=True)


def delete_job(job_id: str) -> bool:
    with _lock:
        if job_id in _backtest_jobs:
            del _backtest_jobs[job_id]
            return True
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Trading-day utilities (lightweight — no exchange dependency)
# ──────────────────────────────────────────────────────────────────────────────

def _get_trading_dates(start: str, end: str, interval_days: int) -> List[str]:
    """Return a list of weekday dates between start and end, sampled every interval_days."""
    fmt = "%Y-%m-%d"
    cur = datetime.strptime(start, fmt)
    end_dt = datetime.strptime(end, fmt)
    dates = []
    while cur <= end_dt:
        if cur.weekday() < 5:  # Mon–Fri only
            dates.append(cur.strftime(fmt))
        cur += timedelta(days=interval_days)
    return dates


def _get_price_after(symbol: str, base_date: str, hold_days: int) -> Optional[float]:
    """Fetch closing price hold_days trading days after base_date using akshare."""
    try:
        import akshare as ak
        from tradingagents.dataflows.interface import route_to_vendor
        import pandas as pd

        fmt = "%Y-%m-%d"
        start_dt = datetime.strptime(base_date, fmt)
        # Fetch data starting from base_date + 1 day, extend window for hold_days
        fetch_start = (start_dt + timedelta(days=1)).strftime(fmt)
        fetch_end = (start_dt + timedelta(days=hold_days + 30)).strftime(fmt)

        csv_data = route_to_vendor("get_stock_data", symbol, fetch_start, fetch_end)
        if not csv_data:
            return None

        df = pd.read_csv(pd.io.common.StringIO(csv_data))
        # Find column for close price
        close_cols = [c for c in df.columns if "close" in c.lower() or "收盘" in c]
        date_cols = [c for c in df.columns if "date" in c.lower() or "日期" in c or "time" in c.lower()]
        if not close_cols or not date_cols:
            return None

        df = df.sort_values(date_cols[0]).reset_index(drop=True)
        if len(df) < hold_days:
            hold_days = len(df) - 1
        if hold_days < 1:
            return None
        return float(df[close_cols[0]].iloc[hold_days - 1])
    except Exception:
        return None


def _get_price_on(symbol: str, date: str) -> Optional[float]:
    """Fetch closing price on or just before date."""
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        import pandas as pd

        fmt = "%Y-%m-%d"
        start = (datetime.strptime(date, fmt) - timedelta(days=5)).strftime(fmt)
        csv_data = route_to_vendor("get_stock_data", symbol, start, date)
        if not csv_data:
            return None
        df = pd.read_csv(pd.io.common.StringIO(csv_data))
        close_cols = [c for c in df.columns if "close" in c.lower() or "收盘" in c]
        date_cols = [c for c in df.columns if "date" in c.lower() or "日期" in c or "time" in c.lower()]
        if not close_cols or not date_cols:
            return None
        df = df.sort_values(date_cols[0]).reset_index(drop=True)
        return float(df[close_cols[0]].iloc[-1])
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Core backtest runner
# ──────────────────────────────────────────────────────────────────────────────

def _run_single_analysis(symbol: str, trade_date: str, selected_analysts: List[str], config: Dict[str, Any]) -> Dict[str, Any]:
    """Run one full analysis without SSE. Returns final state dict."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.dataflows.config import set_config

    set_config(config)
    graph = TradingAgentsGraph(
        selected_analysts=selected_analysts,
        debug=False,
        config=config,
    )
    final_state, _ = graph.propagate(symbol, trade_date)
    decision_raw = final_state.get("final_trade_decision", "")
    decision = graph.process_signal(decision_raw)
    return {
        "final_trade_decision": decision_raw,
        "decision": decision,
    }


def _classify_decision(decision: str) -> str:
    """Classify decision as BUY / SELL / HOLD."""
    d = decision.upper()
    if any(k in d for k in ["BUY", "增持", "买入", "BULLISH"]):
        return "BUY"
    if any(k in d for k in ["SELL", "减持", "卖出", "BEARISH"]):
        return "SELL"
    return "HOLD"


def _compute_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute win rate and average return from backtest records."""
    trades = [r for r in records if r.get("action") in ("BUY", "SELL") and r.get("return_pct") is not None]
    if not trades:
        return {"total_signals": 0, "win_rate": None, "avg_return_pct": None, "best_return_pct": None, "worst_return_pct": None}

    wins = 0
    returns = []
    for t in trades:
        ret = t["return_pct"]
        returns.append(ret)
        # Win = positive return for BUY, negative return for SELL
        if t["action"] == "BUY" and ret > 0:
            wins += 1
        elif t["action"] == "SELL" and ret < 0:
            wins += 1

    return {
        "total_signals": len(trades),
        "win_rate": round(wins / len(trades) * 100, 1),
        "avg_return_pct": round(sum(returns) / len(returns), 2),
        "best_return_pct": round(max(returns), 2),
        "worst_return_pct": round(min(returns), 2),
    }


def _run_backtest(job_id: str, symbol: str, start_date: str, end_date: str,
                  selected_analysts: List[str], hold_days: int, sample_interval: int,
                  config: Dict[str, Any]) -> None:
    """Background thread: run backtest and store results."""
    _set(job_id, status="running", started_at=_utcnow_iso())

    dates = _get_trading_dates(start_date, end_date, sample_interval)
    total = len(dates)
    _set(job_id, total_dates=total, completed_dates=0, records=[], error=None)

    records: List[Dict[str, Any]] = []

    for i, trade_date in enumerate(dates):
        record: Dict[str, Any] = {"date": trade_date, "action": "HOLD", "return_pct": None, "error": None}
        try:
            analysis = _run_single_analysis(symbol, trade_date, selected_analysts, config)
            action = _classify_decision(analysis["decision"])
            record["action"] = action
            record["decision_summary"] = analysis["final_trade_decision"][:200] if analysis.get("final_trade_decision") else ""

            if action in ("BUY", "SELL"):
                entry_price = _get_price_on(symbol, trade_date)
                exit_price = _get_price_after(symbol, trade_date, hold_days)
                if entry_price and exit_price and entry_price > 0:
                    raw_return = (exit_price - entry_price) / entry_price * 100
                    record["entry_price"] = round(entry_price, 2)
                    record["exit_price"] = round(exit_price, 2)
                    record["return_pct"] = round(raw_return if action == "BUY" else -raw_return, 2)
        except Exception as exc:
            record["error"] = str(exc)[:200]

        records.append(record)
        _set(job_id, completed_dates=i + 1, records=list(records))

    stats = _compute_stats(records)
    _set(job_id,
         status="completed",
         finished_at=_utcnow_iso(),
         records=records,
         stats=stats)


def submit(
    symbol: str,
    start_date: str,
    end_date: str,
    selected_analysts: List[str],
    hold_days: int,
    sample_interval: int,
    config: Dict[str, Any],
) -> str:
    """Submit a backtest job. Returns job_id."""
    job_id = uuid4().hex
    _set(job_id,
         job_id=job_id,
         symbol=symbol,
         start_date=start_date,
         end_date=end_date,
         selected_analysts=selected_analysts,
         hold_days=hold_days,
         sample_interval=sample_interval,
         status="pending",
         created_at=_utcnow_iso(),
         total_dates=0,
         completed_dates=0,
         records=[],
         stats=None,
         error=None)

    thread = threading.Thread(
        target=_run_backtest,
        args=(job_id, symbol, start_date, end_date, selected_analysts, hold_days, sample_interval, config),
        daemon=True,
    )
    thread.start()
    return job_id
