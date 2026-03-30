"""DataCollector: fetch all data once, serve windowed views to analyst agents."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import time
import pandas as pd
from stockstats import wrap
import io

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
    start_t = time.time()
    try:
        res = tool.invoke(payload)
        duration = time.time() - start_t
        # 仅在耗时较长时输出
        if duration > 0.5:
            print(f"  [Timer] {getattr(tool, 'name', str(tool))} took {duration:.2f}s")
        return res
    except Exception as exc:
        return f"{getattr(tool, 'name', str(tool))} 调用失败：{type(exc).__name__}: {exc}"


def _fetch_all(ticker: str, trade_date: str) -> Dict[str, Any]:
    """Fetch all data sources in parallel.

    Always fetches full data including financial statements, regardless of horizon.
    The horizon only affects the analysis window, not data collection.
    """
    lookback = LONG_DAYS
    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    # 为了计算指标准确（如 200 SMA），需要比分析窗口更长的历史数据
    fetch_lookback = 365
    start_str = (end_dt - timedelta(days=fetch_lookback)).strftime("%Y-%m-%d")

    tasks: Dict[str, tuple] = {
        "stock_data": (get_stock_data, {"symbol": ticker, "start_date": start_str, "end_date": trade_date}),
        "news": (get_news, {"ticker": ticker, "start_date": (end_dt - timedelta(days=lookback)).strftime("%Y-%m-%d"), "end_date": trade_date}),
        "global_news": (get_global_news, {"curr_date": trade_date, "look_back_days": lookback, "limit": 30}),
        "fund_flow_board": (get_board_fund_flow, {}),
        "fund_flow_individual": (get_individual_fund_flow, {"symbol": ticker}),
        "lhb": (get_lhb_detail, {"symbol": ticker, "date": trade_date}),
        "insider_transactions": (get_insider_transactions, {"ticker": ticker}),
        "zt_pool": (get_zt_pool, {"date": trade_date}),
        "hot_stocks": (get_hot_stocks_xq, {}),
    }

    # 财务报表类数据始终拉取，Research Manager 根据 horizon 自行判断权重
    tasks.update({
        "fundamentals": (get_fundamentals, {"ticker": ticker, "curr_date": trade_date}),
        "balance_sheet": (get_balance_sheet, {"ticker": ticker, "freq": "quarterly", "curr_date": trade_date}),
        "cashflow": (get_cashflow, {"ticker": ticker, "freq": "quarterly", "curr_date": trade_date}),
        "income_statement": (get_income_statement, {"ticker": ticker, "freq": "quarterly", "curr_date": trade_date}),
    })

    results: Dict[str, Any] = {}
    fetch_start = time.time()
    # 减少并发池大小，避免被反爬
    with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as executor:
        future_to_key = {executor.submit(_safe, tool, payload): key for key, (tool, payload) in tasks.items()}
        for future in future_to_key:
            results[future_to_key[future]] = future.result()

    # ── 核心加速：本地计算所有技术指标 ──────────────────
    indicators_res = {}
    try:
        raw_csv = results.get("stock_data", "")
        if isinstance(raw_csv, str) and len(raw_csv) > 50:
            # 使用 on_bad_lines='skip' 容忍异常行，使用 comment='#' 跳过注释行
            df = pd.read_csv(io.StringIO(raw_csv), on_bad_lines='skip', comment='#')
            if not df.empty:
                # 兼容不同数据源的列名（大小写）
                cols_map = {c.lower(): c for c in df.columns}
                rename_dict = {}
                for target in ["date", "open", "high", "low", "close", "volume"]:
                    if target in cols_map:
                        rename_dict[cols_map[target]] = target
                
                df = df.rename(columns=rename_dict)
                
                # 再次检查关键列是否存在
                if "close" in df.columns:
                    ss = wrap(df)
                    
                    # 批量触发计算
                    calc_map = {
                        "close_50_sma": "close_50_sma",
                        "close_200_sma": "close_200_sma",
                        "close_10_ema": "close_10_ema",
                        "rsi": "rsi_14",
                        "macd": "macd",
                        "boll": "close_20_sma",
                        "boll_ub": "boll_ub",
                        "boll_lb": "boll_lb",
                        "atr": "atr",
                        "vwma": "vwma"
                    }
                    
                    for key, ss_key in calc_map.items():
                        try:
                            val = ss[ss_key].iloc[-1]
                            indicators_res[key] = round(float(val), 2) if isinstance(val, (int, float)) else str(val)
                        except Exception:
                            indicators_res[key] = "N/A"
                else:
                    print(f"  [Warning] 'close' column not found in stock_data columns: {df.columns}")
        else:
            print(f"  [Warning] No valid stock_data for indicator calculation.")
    except Exception as e:
        print(f"  [Error] Local indicator calculation failed: {e}")
    
    # 填充缺失值
    for ind in INDICATORS:
        if ind not in indicators_res:
            indicators_res[ind] = "无数据"
            
    results["indicators"] = indicators_res
    # ────────────────────────────────────────────────

    print(f"[Timer] Total Data Collection for {ticker} took {time.time() - fetch_start:.2f}s")
    return results


class DataCollector:
    """Collect and cache data for a single analysis run."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def collect(self, ticker: str, trade_date: str, horizons: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fetch all data and store in cache.

        Always fetches full data (including financial statements) regardless of horizon.
        Data is collected once and shared across all horizon runs.
        """
        key = make_cache_key(ticker, trade_date)
        if key not in self._cache:
            self._cache[key] = _fetch_all(ticker, trade_date)
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
