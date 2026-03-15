"""DataCollector: fetch all data once, serve windowed views to analyst agents."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from tradingagents.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_global_news,
    get_insider_transactions,
    get_board_fund_flow,
    get_individual_fund_flow,
    get_lhb_detail,
    get_zt_pool,
    get_hot_stocks_xq,
)

INDICATORS = [
    "close_50_sma", "close_200_sma", "close_10_ema",
    "rsi", "macd", "boll", "boll_ub", "boll_lb", "atr", "vwma",
]
SHORT_DAYS = 14
LONG_DAYS = 90


def make_cache_key(ticker: str, trade_date: str) -> str:
    return f"{ticker}_{trade_date}"


def _safe(tool, payload: dict) -> Any:
    try:
        return tool.invoke(payload)
    except Exception as exc:
        return f"{getattr(tool, 'name', str(tool))} 调用失败：{type(exc).__name__}: {exc}"


def _fetch_all(ticker: str, trade_date: str, short_only: bool = False) -> Dict[str, Any]:
    """Fetch data sources in parallel.

    short_only=True (horizons==['short']): 14-day lookback, skips fundamentals/financials.
    short_only=False: 90-day lookback, fetches full data including financial statements.
    """
    lookback = SHORT_DAYS if short_only else LONG_DAYS
    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    start_str = (end_dt - timedelta(days=lookback)).strftime("%Y-%m-%d")

    tasks: Dict[str, tuple] = {
        "stock_data": (get_stock_data, {"symbol": ticker, "start_date": start_str, "end_date": trade_date}),
        "news": (get_news, {"ticker": ticker, "start_date": start_str, "end_date": trade_date}),
        "global_news": (get_global_news, {"curr_date": trade_date, "look_back_days": lookback, "limit": 30}),
        "fund_flow_board": (get_board_fund_flow, {}),
        "fund_flow_individual": (get_individual_fund_flow, {"symbol": ticker}),
        "lhb": (get_lhb_detail, {"symbol": ticker, "date": trade_date}),
        "insider_transactions": (get_insider_transactions, {"ticker": ticker}),
        "zt_pool": (get_zt_pool, {"date": trade_date}),
        "hot_stocks": (get_hot_stocks_xq, {}),
    }

    # 财务报表类数据仅中线/全量模式需要，短线跳过
    if not short_only:
        tasks.update({
            "fundamentals": (get_fundamentals, {"ticker": ticker, "curr_date": trade_date}),
            "balance_sheet": (get_balance_sheet, {"ticker": ticker, "freq": "quarterly", "curr_date": trade_date}),
            "cashflow": (get_cashflow, {"ticker": ticker, "freq": "quarterly", "curr_date": trade_date}),
            "income_statement": (get_income_statement, {"ticker": ticker, "freq": "quarterly", "curr_date": trade_date}),
        })

    results: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(tasks) + len(INDICATORS)) as executor:
        future_to_key = {executor.submit(_safe, tool, payload): key for key, (tool, payload) in tasks.items()}
        ind_futures = {
            executor.submit(_safe, get_indicators, {
                "symbol": ticker, "indicator": ind,
                "curr_date": trade_date, "look_back_days": lookback,
            }): ind for ind in INDICATORS
        }
        for future in future_to_key:
            results[future_to_key[future]] = future.result()
        results["indicators"] = {ind_futures[f]: f.result() for f in ind_futures}

    return results


class DataCollector:
    """Collect and cache data for a single analysis run."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def collect(self, ticker: str, trade_date: str, horizons: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fetch data and store in cache.

        Passes short_only=True when horizons is EXACTLY ['short'] to use a 14-day lookback
        and skip financial statements, speeding up short-term-only analysis.
        """
        key = make_cache_key(ticker, trade_date)
        if key not in self._cache:
            # Only use short_only optimization if we only have one horizon and it's 'short'
            short_only = horizons is not None and len(horizons) == 1 and horizons[0] == "short"
            self._cache[key] = _fetch_all(ticker, trade_date, short_only=short_only)
        return self._cache[key]

    def get(self, ticker: str, trade_date: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached pool, or None if not collected yet."""
        return self._cache.get(make_cache_key(ticker, trade_date))

    def get_window(
        self,
        pool: Dict[str, Any],
        horizon: str,
        trade_date: str,
    ) -> Dict[str, Any]:
        """Return pool copy annotated with horizon window metadata."""
        days = SHORT_DAYS if horizon == "short" else LONG_DAYS
        result = dict(pool)
        result["_data_window"] = f"{days}天"
        result["_horizon"] = horizon
        return result

    def evict(self, ticker: str, trade_date: str) -> None:
        """Remove cached data after analysis completes to free memory."""
        self._cache.pop(make_cache_key(ticker, trade_date), None)
