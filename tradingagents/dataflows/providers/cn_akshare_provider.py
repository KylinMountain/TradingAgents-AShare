import logging as _logging
import re
import time
import threading
import contextvars
from datetime import datetime, timedelta

import pandas as pd
from stockstats import wrap

from .base import BaseMarketDataProvider
from ..trade_calendar import cn_market_phase, cn_no_data_reason, cn_today_str, is_cn_trading_day

logger = _logging.getLogger(__name__)


# ── akshare 并发控制 ──
# 总并发上限 5（防反爬 + akshare 全局状态安全）
# 定时任务最多占 3 个槽位，保证前端至少有 2 个槽位可用
#
# 关键设计：僵尸线程回收
# _run_job 超时后不会 cancel 内部线程（避免 cancel 卡在 to_thread），
# 导致僵尸线程可能永远持有 semaphore permit。_AkshareLock 通过追踪每个
# permit 的持有时间，在超过 STALE_TIMEOUT 后自动回收，防止锁被耗尽。

_is_scheduled_task: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "is_scheduled_task", default=False,
)


def set_scheduled_task_context(value: bool = True) -> contextvars.Token:
    """标记当前上下文为定时任务（会通过 asyncio.to_thread 自动传播到工作线程）"""
    return _is_scheduled_task.set(value)


_lock_logger = _logging.getLogger(__name__)


class _AkshareLock:
    """akshare 并发锁：前端优先 + 僵尸线程自动回收。

    - 总并发上限 ``total``（防反爬）
    - 定时任务额外受 ``scheduled_max`` 限制，为前端保留带宽
    - 持锁超过 ``stale_timeout`` 秒的线程视为僵尸，permit 被自动回收
    - 僵尸线程最终退出 ``with`` 块时不会 double-release（已被回收）
    """

    ACQUIRE_TIMEOUT = 60   # 等待 slot 的最大秒数
    STALE_TIMEOUT = 120    # 单次 akshare 调用不应超过 2 分钟，超过视为僵尸

    def __init__(self, total: int = 5, scheduled_max: int = 3):
        self._total = threading.Semaphore(total)
        self._scheduled = threading.Semaphore(scheduled_max)
        self._holders: dict[int, tuple[float, bool]] = {}   # tid -> (mono_time, is_scheduled)
        self._mu = threading.Lock()

    # ── 僵尸回收 ──

    def _reclaim_stale(self) -> int:
        """回收超时持有者的 permit，返回回收数量。"""
        now = time.monotonic()
        reclaimed = 0
        with self._mu:
            stale = [
                (tid, is_sched)
                for tid, (t, is_sched) in self._holders.items()
                if now - t > self.STALE_TIMEOUT
            ]
            for tid, is_sched in stale:
                del self._holders[tid]
                self._total.release()
                if is_sched:
                    self._scheduled.release()
                reclaimed += 1
        if reclaimed:
            _lock_logger.warning("[AkshareLock] reclaimed %d stale permits from zombie threads", reclaimed)
        return reclaimed

    # ── context manager ──

    def _acquire_or_reclaim(self, sem: threading.Semaphore, label: str) -> None:
        """尝试获取 semaphore，超时后回收僵尸再重试一次。"""
        if sem.acquire(timeout=self.ACQUIRE_TIMEOUT):
            return
        self._reclaim_stale()
        if sem.acquire(timeout=10):
            return
        raise TimeoutError(f"akshare {label} slot acquire timeout after reclaim")

    def __enter__(self):
        is_scheduled = _is_scheduled_task.get(False)
        try:
            if is_scheduled:
                self._acquire_or_reclaim(self._scheduled, "scheduled")
                try:
                    self._acquire_or_reclaim(self._total, "total")
                except BaseException:
                    self._scheduled.release()
                    raise
            else:
                self._acquire_or_reclaim(self._total, "total")
        except TimeoutError:
            _lock_logger.error("[AkshareLock] acquire timeout (is_scheduled=%s)", is_scheduled)
            raise
        with self._mu:
            self._holders[threading.get_ident()] = (time.monotonic(), is_scheduled)
        return self

    def __exit__(self, *exc_info):
        tid = threading.get_ident()
        with self._mu:
            info = self._holders.pop(tid, None)
        if info is not None:
            _, is_scheduled = info
            self._total.release()
            if is_scheduled:
                self._scheduled.release()
        # info is None → permit 已被 _reclaim_stale 回收，不 double-release


AKSHARE_CALL_LOCK = _AkshareLock(total=5, scheduled_max=3)


class CnAkshareProvider(BaseMarketDataProvider):
    """A-share provider backed by AkShare."""

    INDICATOR_DESCRIPTIONS = {
        "close_50_sma": (
            "50 日均线（SMA）：中期趋势指标。"
            "用途：识别趋势方向，并作为动态支撑/阻力参考。"
        ),
        "close_200_sma": (
            "200 日均线（SMA）：长期趋势基准。"
            "用途：确认大级别趋势，并辅助识别金叉/死叉结构。"
        ),
        "close_10_ema": (
            "10 日指数均线（EMA）：短期响应更快。"
            "用途：捕捉短线动量变化与潜在入场时机。"
        ),
        "macd": "MACD：趋势与动量综合指标。",
        "macds": "MACD 信号线（Signal）。",
        "macdh": "MACD 柱状图（Histogram）。",
        "rsi": "RSI：衡量超买/超卖的动量指标。",
        "boll": "布林中轨（20 日均线）。",
        "boll_ub": "布林上轨。",
        "boll_lb": "布林下轨。",
        "atr": "ATR：真实波动幅度均值，用于波动与风控。",
        "vwma": "VWMA：成交量加权均线。",
        "mfi": "MFI：资金流量指标。",
    }

    @property
    def name(self) -> str:
        return "cn_akshare"

    def _ak(self):
        try:
            import akshare as ak  # type: ignore
        except ImportError as exc:
            raise NotImplementedError(
                "cn_akshare requires 'akshare'. Install it with: pip install akshare"
            ) from exc
        return ak

    def _locked(self, func, *args, **kwargs):
        with AKSHARE_CALL_LOCK:
            return func(*args, **kwargs)

    def _normalize_symbol(self, symbol: str) -> str:
        s = symbol.strip().lower()
        m = re.search(r"(\d{6})", s)
        if not m:
            raise NotImplementedError(
                f"cn_akshare only supports A-share 6-digit symbols, got: {symbol}"
            )
        return m.group(1)

    def _sina_symbol(self, symbol: str) -> str:
        code = self._normalize_symbol(symbol)
        if code.startswith(("5", "6", "9")):
            return f"sh{code}"
        return f"sz{code}"

    def _xq_symbol(self, symbol: str) -> str:
        code = self._normalize_symbol(symbol)
        if code.startswith(("5", "6", "9")):
            return f"SH{code}"
        return f"SZ{code}"

    def _is_likely_etf_symbol(self, symbol: str) -> bool:
        code = self._normalize_symbol(symbol)
        # 常见 A 股 ETF 代码段：5xxxxx(沪市) / 15xxxx,16xxxx,18xxxx(深市)
        return code.startswith(("5", "15", "16", "18"))

    def _normalize_hist_df(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        if raw_df is None or raw_df.empty:
            return pd.DataFrame()

        col_map = {
            "日期": "Date",
            "date": "Date",
            "Date": "Date",
            "开盘": "Open",
            "open": "Open",
            "Open": "Open",
            "最高": "High",
            "high": "High",
            "High": "High",
            "最低": "Low",
            "low": "Low",
            "Low": "Low",
            "收盘": "Close",
            "close": "Close",
            "Close": "Close",
            "成交量": "Volume",
            "volume": "Volume",
            "Volume": "Volume",
            "amount": "Volume",
            "Amount": "Volume",
        }
        df = raw_df.rename(columns=col_map).copy()
        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"hist dataframe missing columns: {missing}")

        out = df[required].copy()
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
        out = out.dropna(subset=["Date"]).sort_values("Date")

        for c in ["Open", "High", "Low", "Close", "Volume"]:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        out["Volume"] = out["Volume"].astype(float)

        return out

    def _format_ak_hist(self, df: pd.DataFrame, symbol: str, start: str, end: str) -> str:
        if df is None or df.empty:
            return f"No data found for symbol '{symbol}' between {start} and {end}"
        out = self._normalize_hist_df(df)
        out["Dividends"] = 0.0
        out["Stock Splits"] = 0.0
        out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")

        header = f"# Stock data for {symbol} from {start} to {end}\n"
        header += f"# Total records: {len(out)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + out.to_csv(index=False)

    @staticmethod
    def _slice_hist_df(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        start_dt = pd.to_datetime(start_date, errors="coerce")
        end_dt = pd.to_datetime(end_date, errors="coerce")
        if pd.isna(start_dt) or pd.isna(end_dt):
            return df
        out = df.copy()
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
        out = out.dropna(subset=["Date"])
        out = out[(out["Date"] >= start_dt) & (out["Date"] <= end_dt)]
        return out.sort_values("Date").reset_index(drop=True)

    @staticmethod
    def _shrink_table(df: pd.DataFrame, max_rows: int = 12, max_cols: int = 120) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        rows = min(max_rows, len(df))
        cols = min(max_cols, len(df.columns))
        return df.head(rows).iloc[:, :cols]

    def _fetch_hist_df(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        with AKSHARE_CALL_LOCK:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            symbol_with_market = self._sina_symbol(symbol)
            start_yyyymmdd = start_date.replace("-", "")
            end_yyyymmdd = end_date.replace("-", "")

            # ETF 优先：Sina 历史接口稳定且不依赖东财
            if self._is_likely_etf_symbol(symbol):
                etf_errors = []
                try:
                    df = ak.fund_etf_hist_sina(symbol=symbol_with_market)
                    out = self._normalize_hist_df(df)
                    out = self._slice_hist_df(out, start_date, end_date)
                    if not out.empty:
                        return self._maybe_append_realtime_row(symbol, out, end_date, assume_locked=True)
                    etf_errors.append("fund_etf_hist_sina: empty after date filter")
                except Exception as exc:
                    etf_errors.append(f"fund_etf_hist_sina: {type(exc).__name__}")

                try:
                    df = ak.fund_etf_hist_em(
                        symbol=code,
                        period="daily",
                        start_date=start_yyyymmdd,
                        end_date=end_yyyymmdd,
                        adjust="qfq",
                    )
                    out = self._normalize_hist_df(df)
                    if not out.empty:
                        return self._maybe_append_realtime_row(symbol, out, end_date, assume_locked=True)
                    etf_errors.append("fund_etf_hist_em: empty dataframe")
                except Exception as exc:
                    etf_errors.append(f"fund_etf_hist_em: {type(exc).__name__}")

            # Source 1: Eastmoney (default)
            em_last_exc = None
            for i in range(2):
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=code,
                        period="daily",
                        start_date=start_yyyymmdd,
                        end_date=end_yyyymmdd,
                        adjust="qfq",
                    )
                    out = self._normalize_hist_df(df)
                    return self._maybe_append_realtime_row(symbol, out, end_date, assume_locked=True)
                except Exception as exc:
                    em_last_exc = exc
                    if i < 1:
                        time.sleep(0.6 * (i + 1))

            # Source 2: Sina (volume in 股, normalize to 手)
            try:
                df = ak.stock_zh_a_daily(
                    symbol=symbol_with_market,
                    start_date=start_yyyymmdd,
                    end_date=end_yyyymmdd,
                    adjust="qfq",
                )
                out = self._normalize_hist_df(df)
                if not out.empty:
                    out["Volume"] = out["Volume"] / 100
                return self._maybe_append_realtime_row(symbol, out, end_date, assume_locked=True)
            except Exception as exc:
                logger.debug("Sina hist fallback failed for %s: %s", symbol, exc)

            # Source 3: Tencent
            try:
                df = ak.stock_zh_a_hist_tx(
                    symbol=symbol_with_market,
                    start_date=start_yyyymmdd,
                    end_date=end_yyyymmdd,
                    adjust="qfq",
                )
                out = self._normalize_hist_df(df)
                return self._maybe_append_realtime_row(symbol, out, end_date, assume_locked=True)
            except Exception as exc:
                logger.debug("Tencent hist fallback failed for %s: %s", symbol, exc)

            raise NotImplementedError(
                f"cn_akshare is temporarily unavailable for price history (eastmoney/sina/tencent all failed): {em_last_exc}"
            ) from em_last_exc

    def _fetch_realtime_row_sina(self, symbol: str) -> pd.DataFrame:
        import urllib.request

        sina_symbol = self._sina_symbol(symbol)
        url = f"http://hq.sinajs.cn/list={sina_symbol}"
        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode(resp.headers.get_content_charset() or "gbk")
        except Exception:
            return pd.DataFrame()

        m = re.search(r'hq_str_\w+="(.+)"', raw)
        if not m:
            return pd.DataFrame()
        parts = m.group(1).split(",")
        if len(parts) < 32:
            return pd.DataFrame()

        try:
            date_val = pd.to_datetime(parts[30], errors="coerce")
            if pd.isna(date_val):
                date_val = pd.to_datetime(cn_today_str())
            row = {
                "Date": pd.to_datetime(date_val).normalize(),
                "Open": pd.to_numeric(parts[1], errors="coerce"),
                "High": pd.to_numeric(parts[4], errors="coerce"),
                "Low": pd.to_numeric(parts[5], errors="coerce"),
                "Close": pd.to_numeric(parts[3], errors="coerce"),
                "Volume": pd.to_numeric(parts[8], errors="coerce") / 100,  # Sina返回股，转手对齐Eastmoney
            }
        except (ValueError, IndexError):
            return pd.DataFrame()
        rt = pd.DataFrame([row]).dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        return rt

    def _fetch_realtime_row_unlocked(self, symbol: str) -> pd.DataFrame:
        try:
            ak = self._ak()
            spot = ak.stock_individual_spot_xq(symbol=self._xq_symbol(symbol))
        except Exception:
            return self._fetch_realtime_row_sina(symbol)

        if spot is None or spot.empty:
            return self._fetch_realtime_row_sina(symbol)
        if not {"item", "value"}.issubset(set(spot.columns)):
            return self._fetch_realtime_row_sina(symbol)
        kv = dict(zip(spot["item"].astype(str), spot["value"]))

        date_val = pd.to_datetime(kv.get("时间"), errors="coerce")
        if pd.isna(date_val):
            date_val = pd.to_datetime(cn_today_str())
        row = {
            "Date": pd.to_datetime(date_val).normalize(),
            "Open": pd.to_numeric(kv.get("今开"), errors="coerce"),
            "High": pd.to_numeric(kv.get("最高"), errors="coerce"),
            "Low": pd.to_numeric(kv.get("最低"), errors="coerce"),
            "Close": pd.to_numeric(kv.get("现价"), errors="coerce"),
            "Volume": pd.to_numeric(kv.get("成交量"), errors="coerce"),
        }
        rt = pd.DataFrame([row]).dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        if rt.empty:
            return self._fetch_realtime_row_sina(symbol)
        return rt

    def _fetch_realtime_row(self, symbol: str) -> pd.DataFrame:
        with AKSHARE_CALL_LOCK:
            return self._fetch_realtime_row_unlocked(symbol)

    def _maybe_append_realtime_row(
        self,
        symbol: str,
        hist_df: pd.DataFrame,
        end_date: str,
        *,
        assume_locked: bool = False,
    ) -> pd.DataFrame:
        if hist_df is None:
            hist_df = pd.DataFrame()
        try:
            end_dt = pd.to_datetime(end_date, errors="coerce")
            if pd.isna(end_dt):
                return hist_df
            today = pd.to_datetime(cn_today_str())
            if end_dt.normalize() < today:
                return hist_df
            if not is_cn_trading_day(today.strftime("%Y-%m-%d")):
                return hist_df

            has_today = False
            if not hist_df.empty:
                has_today = (pd.to_datetime(hist_df["Date"]).dt.normalize() == today).any()
            if has_today:
                return hist_df

            phase = cn_market_phase()
            if phase in ("pre_open", "closed"):
                return hist_df

            if assume_locked:
                rt = self._fetch_realtime_row_unlocked(symbol)
            else:
                rt = self._fetch_realtime_row(symbol)
            if rt.empty:
                return hist_df
            if pd.to_datetime(rt.iloc[0]["Date"]).normalize() != today:
                return hist_df

            merged = pd.concat([hist_df, rt], ignore_index=True)
            merged = merged.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
            return merged.reset_index(drop=True)
        except Exception as exc:
            logger.warning("Failed to append realtime row for %s: %s", symbol, exc)
            return hist_df

    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str:
        df = self._fetch_hist_df(symbol, start_date, end_date)
        return self._format_ak_hist(df, symbol, start_date, end_date)

    def get_indicators(
        self, symbol: str, indicator: str, curr_date: str, look_back_days: int
    ) -> str:
        if indicator not in self.INDICATOR_DESCRIPTIONS:
            raise ValueError(
                f"Indicator {indicator} is not supported. "
                f"Please choose from: {list(self.INDICATOR_DESCRIPTIONS.keys())}"
            )

        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = curr_dt - timedelta(days=max(look_back_days, 260))
        df = self._fetch_hist_df(symbol, start_dt.strftime("%Y-%m-%d"), curr_date)
        if df is None or df.empty:
            return f"No data found for {symbol} for indicator {indicator}"

        ind_df = df.rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )[["date", "open", "high", "low", "close", "volume"]].copy()
        ind_df["date"] = pd.to_datetime(ind_df["date"], errors="coerce")
        ind_df = ind_df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

        ss = wrap(ind_df)
        indicator_series = ss[indicator]

        values_by_date = {}
        for idx, dt_val in enumerate(ind_df["date"]):
            date_str = pd.to_datetime(dt_val).strftime("%Y-%m-%d")
            val = indicator_series.iloc[idx]
            values_by_date[date_str] = "N/A" if pd.isna(val) else str(val)

        begin = curr_dt - timedelta(days=look_back_days)
        lines = []
        d = curr_dt
        while d >= begin:
            key = d.strftime("%Y-%m-%d")
            if key in values_by_date:
                value = values_by_date[key]
                if value == "N/A":
                    value = cn_no_data_reason(key)
            else:
                value = cn_no_data_reason(key)
            lines.append(f"{key}: {value}")
            d -= timedelta(days=1)

        result = (
            f"## {indicator} 指标值（{begin.strftime('%Y-%m-%d')} 至 {curr_date}）：\n\n"
            + "\n".join(lines)
            + "\n\n"
            + self.INDICATOR_DESCRIPTIONS[indicator]
        )
        return result

    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        with AKSHARE_CALL_LOCK:
            ak = self._ak()
            code = self._normalize_symbol(ticker)
            errors = []

            info_df = None
            try:
                info_df = ak.stock_individual_info_em(symbol=code)
            except Exception as exc:
                errors.append(f"stock_individual_info_em: {type(exc).__name__}")

            if info_df is None or info_df.empty:
                try:
                    info_df = ak.stock_individual_basic_info_xq(symbol=self._xq_symbol(ticker))
                    if not info_df.empty and set(info_df.columns) >= {"item", "value"}:
                        info_df = info_df.rename(columns={"item": "item", "value": "value"})
                except Exception as exc:
                    errors.append(f"stock_individual_basic_info_xq: {type(exc).__name__}")

            abstract_df = None
            try:
                abstract_df = ak.stock_financial_abstract(symbol=code)
            except Exception as exc:
                errors.append(f"stock_financial_abstract: {type(exc).__name__}")

            parts = [f"## Fundamentals for {ticker}"]
            if info_df is not None and not info_df.empty:
                for c in info_df.columns:
                    info_df[c] = info_df[c].astype(str).str.slice(0, 220)
                parts.append("### Company Profile")
                parts.append(info_df.head(40).to_markdown(index=False))
            if abstract_df is not None and not abstract_df.empty:
                parts.append("### Financial Abstract (latest available columns)")
                metric_cols = [c for c in abstract_df.columns if c not in ("选项", "指标")]
                top_cols = metric_cols[:8]
                cols = [c for c in ("选项", "指标") if c in abstract_df.columns] + top_cols
                parts.append(self._shrink_table(abstract_df[cols], max_rows=20, max_cols=10).to_markdown(index=False))

            if len(parts) > 1:
                return "\n\n".join(parts)

            raise NotImplementedError(
                "cn_akshare is temporarily unavailable for fundamentals: "
                + "; ".join(errors)
            )

    def _financial_report_sina(self, ticker: str, report_name: str) -> str:
        with AKSHARE_CALL_LOCK:
            ak = self._ak()
            symbol = self._sina_symbol(ticker)
            errors = []
            try:
                df = ak.stock_financial_report_sina(stock=symbol, symbol=report_name)
                if df is None or df.empty:
                    raise ValueError("empty dataframe")
                return self._shrink_table(df, max_rows=12).to_markdown(index=False)
            except Exception as exc:
                errors.append(f"stock_financial_report_sina: {type(exc).__name__}")

            code = self._normalize_symbol(ticker)
            indicator = "按报告期"
            try:
                # 同花顺摘要表作为备用，口径不完全一致但可作为降级保障
                df = ak.stock_financial_abstract_new_ths(symbol=code, indicator=indicator)
                if df is None or df.empty:
                    raise ValueError("empty dataframe")
                return self._shrink_table(df, max_rows=12).to_markdown(index=False)
            except Exception as exc:
                errors.append(f"stock_financial_abstract_new_ths: {type(exc).__name__}")

            raise NotImplementedError(
                f"cn_akshare is temporarily unavailable for {report_name}: {'; '.join(errors)}"
            )

    def get_balance_sheet(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        table = self._financial_report_sina(ticker, "资产负债表")
        return f"## Balance Sheet ({ticker})\n\n{table}"

    def get_cashflow(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        table = self._financial_report_sina(ticker, "现金流量表")
        return f"## Cashflow ({ticker})\n\n{table}"

    def get_income_statement(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        table = self._financial_report_sina(ticker, "利润表")
        return f"## Income Statement ({ticker})\n\n{table}"

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        with AKSHARE_CALL_LOCK:
            ak = self._ak()
            code = self._normalize_symbol(ticker)
            try:
                df = ak.stock_news_em(symbol=code)
                if df is None or df.empty:
                    return f"No news found for {ticker}"

                date_col = "发布时间" if "发布时间" in df.columns else None
                if date_col is not None:
                    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                    df = df[(df[date_col] >= start_dt) & (df[date_col] < end_dt)]

                if df.empty:
                    return f"No news found for {ticker} between {start_date} and {end_date}"

                rows = []
                for _, row in df.head(20).iterrows():
                    title = str(row.get("新闻标题", row.get("标题", "No title")))
                    src = str(row.get("文章来源", row.get("来源", "Unknown")))
                    summary = str(row.get("新闻内容", row.get("内容", "")))
                    link = str(row.get("新闻链接", row.get("链接", "")))
                    rows.append(f"### {title} (source: {src})")
                    if summary and summary != "nan":
                        rows.append(summary[:400])
                    if link and link != "nan":
                        rows.append(f"Link: {link}")
                    rows.append("")

                return f"## {ticker} 新闻（{start_date} 至 {end_date}）：\n\n" + "\n".join(rows)
            except Exception as exc:
                raise NotImplementedError(
                    f"cn_akshare is temporarily unavailable for news: {exc}"
                ) from exc

    def get_global_news(
        self, curr_date: str, look_back_days: int = 7, limit: int = 50
    ) -> str:
        with AKSHARE_CALL_LOCK:
            ak = self._ak()
            try:
                if hasattr(ak, "news_cctv"):
                    target_dt = datetime.strptime(curr_date, "%Y-%m-%d")
                    used_date = curr_date
                    df = ak.news_cctv(date=curr_date.replace("-", ""))
                    if df is None or df.empty:
                        # Fallback: if today's feed is empty, try recent 3 days.
                        for back in range(1, 4):
                            probe_dt = target_dt - timedelta(days=back)
                            probe_date = probe_dt.strftime("%Y-%m-%d")
                            probe_df = ak.news_cctv(date=probe_date.replace("-", ""))
                            if probe_df is not None and not probe_df.empty:
                                df = probe_df
                                used_date = probe_date
                                break
                    if df is None or df.empty:
                        return f"{curr_date} 未获取到全球市场新闻（已回看最近3天）"
                    rows = []
                    for _, row in df.head(limit).iterrows():
                        title = str(row.get("title", row.get("标题", "No title")))
                        content = str(row.get("content", row.get("内容", "")))
                        rows.append(f"### {title}")
                        if content and content != "nan":
                            rows.append(content[:300])
                        rows.append("")
                    start = (
                        datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)
                    ).strftime("%Y-%m-%d")
                    if used_date != curr_date:
                        return (
                            f"## 全球市场新闻（{start} 至 {curr_date}，当日为空，回退至 {used_date}）：\n\n"
                            + "\n".join(rows)
                        )
                    return f"## 全球市场新闻（{start} 至 {curr_date}）：\n\n" + "\n".join(rows)
                return "当前 cn_akshare 实现暂不支持全球新闻接口。"
            except Exception as exc:
                raise NotImplementedError(
                    f"cn_akshare is temporarily unavailable for global news: {exc}"
                ) from exc

    def get_insider_transactions(self, symbol: str) -> str:
        ak = self._ak()
        code = self._normalize_symbol(symbol)
        errors = []
        try:
            # stock_ggcg_em 不支持按个股代码查询，默认全市场数据量较大
            with AKSHARE_CALL_LOCK:
                df = ak.stock_main_stock_holder(stock=code)
            if df is not None and not df.empty:
                return (
                    f"## Insider Transactions for {symbol}\n\n"
                    f"{df.head(20).to_markdown(index=False)}"
                )
            errors.append("stock_main_stock_holder: empty dataframe")
        except Exception as exc:
            errors.append(f"stock_main_stock_holder: {type(exc).__name__}")

        try:
            # 退化为最近相关新闻，至少保证接口有可用输出
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            news = self.get_news(symbol, start_date, end_date)
            return (
                f"## Insider Transactions for {symbol}\n\n"
                f"未获取到股东交易明细，降级返回近两周公司相关新闻：\n\n{news}"
            )
        except Exception as exc:
            errors.append(f"news_fallback: {type(exc).__name__}")

        raise NotImplementedError(
            f"cn_akshare is temporarily unavailable for insider transactions: {'; '.join(errors)}"
        )

    # TTL cache for stock_zh_a_spot_em to avoid hammering Eastmoney under concurrent load
    _spot_cache: "pd.DataFrame | None" = None
    _spot_cache_ts: float = 0.0
    _SPOT_CACHE_TTL: float = 8.0  # seconds

    def get_realtime_quotes(self, symbols: list[str]) -> str:
        """Fetch real-time A-share quotes. Tries Eastmoney first, falls back to Sina."""
        import json
        import time as _time
        import logging

        logger = logging.getLogger(__name__)

        # Build normalized code → original symbol map
        code_to_original: dict[str, str] = {}
        for s in symbols:
            if not s or not s.strip():
                continue
            try:
                code = self._normalize_symbol(s)
            except NotImplementedError:
                continue
            if code and code not in code_to_original:
                code_to_original[code] = s.strip().upper()

        if not code_to_original:
            return json.dumps({})

        # Try Sina first (lightweight, rarely blocked)
        try:
            result = self._fetch_quotes_sina(code_to_original)
            if result and result != "{}":
                return result
        except Exception as exc:
            logger.debug("[realtime-quotes] Sina failed, falling back to Eastmoney: %s", exc)

        # Fallback: Eastmoney via akshare (cached)
        now = _time.time()
        if (
            CnAkshareProvider._spot_cache is not None
            and (now - CnAkshareProvider._spot_cache_ts) < CnAkshareProvider._SPOT_CACHE_TTL
        ):
            df = CnAkshareProvider._spot_cache
        else:
            try:
                with AKSHARE_CALL_LOCK:
                    ak = self._ak()
                    df = ak.stock_zh_a_spot_em()
            except TimeoutError as exc:
                _lock_logger.warning("[realtime-quotes] Eastmoney slot timeout: %s", exc)
                return json.dumps({})
            except Exception as exc:
                _lock_logger.warning("[realtime-quotes] Eastmoney fetch failed: %s", exc)
                return json.dumps({})
            CnAkshareProvider._spot_cache = df
            CnAkshareProvider._spot_cache_ts = now

        if df is not None and not df.empty:
            return self._build_quotes_from_em(df, code_to_original)
        return json.dumps({})

    def _build_quotes_from_em(self, df: "pd.DataFrame", code_to_original: dict[str, str]) -> str:
        import json
        normalized = list(code_to_original.keys())
        df = df[df["代码"].isin(normalized)]
        result: dict[str, dict] = {}
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            original = code_to_original.get(code)
            if not original:
                continue
            price = self._safe_float(row.get("最新价"))
            prev_close = self._safe_float(row.get("昨收"))
            change = round(price - prev_close, 4) if price is not None and prev_close else None
            change_pct = round(change / prev_close * 100, 4) if change is not None and prev_close else None
            result[original] = {
                "price": price,
                "open": self._safe_float(row.get("今开")),
                "high": self._safe_float(row.get("最高")),
                "low": self._safe_float(row.get("最低")),
                "previous_close": prev_close,
                "change": change,
                "change_pct": change_pct,
                "volume": self._safe_float(row.get("成交量")),
                "amount": self._safe_float(row.get("成交额")),
                "source": "eastmoney",
            }
        return json.dumps(result, ensure_ascii=False)

    def _fetch_quotes_sina(self, code_to_original: dict[str, str]) -> str:
        """Fetch quotes from Sina Finance hq.sinajs.cn as fallback."""
        import json
        import requests as _requests

        sina_codes = []
        sina_to_original: dict[str, str] = {}
        for code, original in code_to_original.items():
            prefix = "sh" if code.startswith(("5", "6", "9")) else "bj" if code.startswith(("4", "8")) else "sz"
            sina_code = f"{prefix}{code}"
            sina_codes.append(sina_code)
            sina_to_original[sina_code] = original

        if not sina_codes:
            return json.dumps({})

        try:
            resp = _requests.get(
                "https://hq.sinajs.cn/list=" + ",".join(sina_codes),
                headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"},
                timeout=5,
            )
            resp.encoding = "gbk"
        except Exception as exc:
            logger.debug("Sina realtime quotes fetch failed: %s", exc)
            return json.dumps({})

        result: dict[str, dict] = {}
        for line in resp.text.splitlines():
            line = line.strip()
            if not line or '="' not in line:
                continue
            try:
                var_part, data_part = line.split('="', 1)
                sina_code = var_part.split("_")[-1]
                fields = data_part.rstrip('";').split(",")
                if len(fields) < 10:
                    continue
                original = sina_to_original.get(sina_code)
                if not original:
                    continue
                price = self._safe_float(fields[3])
                prev_close = self._safe_float(fields[2])
                change = round(price - prev_close, 4) if price is not None and prev_close else None
                change_pct = round(change / prev_close * 100, 4) if change is not None and prev_close else None
                # Sina fields[30]=date, fields[31]=time
                quote_time = None
                if len(fields) > 31 and fields[30] and fields[31]:
                    quote_time = f"{fields[30]} {fields[31]}"
                result[original] = {
                    "price": price,
                    "open": self._safe_float(fields[1]),
                    "high": self._safe_float(fields[4]),
                    "low": self._safe_float(fields[5]),
                    "previous_close": prev_close,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": self._safe_float(fields[8]) / 100 if self._safe_float(fields[8]) is not None else None,  # Sina返回股，转手对齐Eastmoney
                    "amount": self._safe_float(fields[9]),
                    "quote_time": quote_time,
                    "source": "sina",
                }
            except (ValueError, IndexError):
                continue
        return json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _safe_float(val) -> float | None:
        if val is None:
            return None
        try:
            f = float(val)
            return f if not pd.isna(f) else None
        except (ValueError, TypeError):
            return None

    def get_board_fund_flow(self) -> str:
        """获取行业板块资金流向排名。"""
        try:
            ak = self._ak()
            with AKSHARE_CALL_LOCK:
                df = ak.stock_fund_flow_industry()
            if df is None or df.empty:
                return "今日板块资金流向数据暂不可用。"
            sort_col = "主力资金"
            if sort_col in df.columns:
                df_sorted = df.sort_values(sort_col, ascending=False).reset_index(drop=True)
            else:
                df_sorted = df.reset_index(drop=True)
            df_sorted.insert(0, "排名", range(1, len(df_sorted) + 1))
            total = len(df_sorted)
            result = df_sorted.head(10).to_string(index=False)
            return f"板块资金流向排名（共{total}个板块，前10名）：\n{result}"
        except Exception as exc:
            return f"板块资金流向数据获取失败：{type(exc).__name__}: {exc}"

    def get_individual_fund_flow(self, symbol: str) -> str:
        """获取个股近期主力资金净流向。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            # 沪市：以 5、6、9 开头；其余为深市
            market = "sh" if code[:1] in ("5", "6", "9") else "sz"
            with AKSHARE_CALL_LOCK:
                df = ak.stock_individual_fund_flow(stock=code, market=market)
            if df is None or df.empty:
                return f"{symbol} 近期主力资金流向数据暂不可用。"
            df_recent = df.tail(5)
            return f"{symbol} 近5日主力资金净流向：\n{df_recent.to_string(index=False)}"
        except Exception as exc:
            return f"个股资金流向数据获取失败：{type(exc).__name__}: {exc}"

    def get_lhb_detail(self, symbol: str, date: str) -> str:
        """获取龙虎榜数据，非异动日返回空提示（属正常）。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            with AKSHARE_CALL_LOCK:
                df = ak.stock_lhb_detail_em(symbol=code, start_date=date, end_date=date)
            if df is None or df.empty:
                return f"{symbol} 在 {date} 无龙虎榜数据（非异动日属正常）。"
            return f"{symbol} 龙虎榜明细（{date}）：\n{df.head(20).to_string(index=False)}"
        except Exception as exc:
            return f"龙虎榜数据获取失败：{type(exc).__name__}: {exc}"

    def get_zt_pool(self, date: str) -> str:
        """获取涨停板情绪池，反映市场整体情绪温度。"""
        try:
            ak = self._ak()
            with AKSHARE_CALL_LOCK:
                df = ak.stock_zt_pool_em(date=date.replace("-", ""))
            if df is None or df.empty:
                return f"{date} 涨停板情绪池数据暂不可用。"
            count = len(df)
            result = f"{date} 涨停家数：{count}\n"
            if "连板数" in df.columns:
                lianban = df["连板数"].value_counts().sort_index()
                result += f"连板分布：\n{lianban.head(10).to_string()}"
            return result
        except Exception as exc:
            return f"涨停板情绪池数据获取失败：{type(exc).__name__}: {exc}"

    def get_hot_stocks_xq(self) -> str:
        """获取雪球热搜股票，反映散户关注度。"""
        try:
            ak = self._ak()
            with AKSHARE_CALL_LOCK:
                df = ak.stock_hot_follow_xq(symbol="最热门")
            if df is None or df.empty:
                return "雪球热搜数据暂不可用。"
            return f"雪球热搜前20：\n{df.head(20).to_string(index=False)}"
        except Exception as exc:
            return f"雪球热搜数据获取失败：{type(exc).__name__}: {exc}"

    # ── 新增数据源：北向资金、融资融券、大宗交易、龙虎榜席位、机构调研、股东增减持、限售解禁、股权质押 ──

    def get_hsgt_individual(self, symbol: str) -> str:
        """获取个股北向资金持仓历史（沪/深港通）。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            with AKSHARE_CALL_LOCK:
                df = ak.stock_hsgt_individual_em(symbol=code)
            if df is None or df.empty:
                return f"{symbol} 北向资金持仓数据暂不可用。"
            # 数据时效性检查：该 API 数据更新滞后，若最新日期超过 30 天视为过期
            date_col = None
            for col in df.columns:
                if "日期" in str(col):
                    date_col = col
                    break
            if date_col is not None:
                latest = str(df[date_col].max())
                from datetime import datetime, timedelta
                try:
                    latest_dt = datetime.strptime(latest[:10], "%Y-%m-%d")
                    if (datetime.now() - latest_dt).days > 30:
                        return f"{symbol} 北向资金持仓数据已过期（最新：{latest[:10]}），无近期数据。"
                except (ValueError, TypeError):
                    pass
            recent = df.tail(10)
            return f"{symbol} 北向资金持仓（近10日）：\n{recent.to_string(index=False)}"
        except Exception as exc:
            return f"北向资金数据获取失败：{type(exc).__name__}: {exc}"

    def get_hsgt_flow(self) -> str:
        """获取沪/深股通近期整体净流入趋势。"""
        try:
            ak = self._ak()
            results = []
            for channel in ("沪股通", "深股通"):
                with AKSHARE_CALL_LOCK:
                    df = ak.stock_hsgt_hist_em(symbol=channel)
                if df is not None and not df.empty:
                    recent = df.tail(5)
                    results.append(f"【{channel}】\n{recent.to_string(index=False)}")
            if not results:
                return "北向资金整体流入数据暂不可用。"
            return "北向资金整体净流入趋势（近5日）：\n" + "\n\n".join(results)
        except Exception as exc:
            return f"北向资金流入数据获取失败：{type(exc).__name__}: {exc}"

    def get_margin_detail(self, symbol: str, date: str) -> str:
        """获取个股融资融券明细（自动合并沪深交易所）。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            date_str = date.replace("-", "")
            frames = []
            for api_fn in (ak.stock_margin_detail_sse, ak.stock_margin_detail_szse):
                try:
                    with AKSHARE_CALL_LOCK:
                        df = api_fn(date=date_str)
                    if df is not None and not df.empty and len(df.columns) > 0:
                        frames.append(df)
                except Exception:
                    continue
            if not frames:
                return f"{symbol} 在 {date} 融资融券数据暂不可用（非交易日或数据未更新）。"
            combined = pd.concat(frames, ignore_index=True)
            code_col = None
            for col in combined.columns:
                if "证券" in str(col) and "代码" in str(col):
                    code_col = col
                    break
            if code_col:
                filtered = combined[combined[code_col].astype(str).str.contains(code)]
            else:
                filtered = combined
            if filtered.empty:
                return f"{symbol} 在 {date} 无融资融券记录。"
            return f"{symbol} 融资融券明细（{date}）：\n{filtered.head(5).to_string(index=False)}"
        except Exception as exc:
            return f"融资融券数据获取失败：{type(exc).__name__}: {exc}"

    def get_block_trades(self, symbol: str, start_date: str, end_date: str) -> str:
        """获取个股大宗交易明细。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            sd = start_date.replace("-", "")
            ed = end_date.replace("-", "")
            with AKSHARE_CALL_LOCK:
                df = ak.stock_dzjy_mrmx(symbol="A股", start_date=sd, end_date=ed)
            if df is None or df.empty:
                return f"{symbol} 在 {start_date}~{end_date} 无大宗交易数据。"
            code_col = None
            for col in df.columns:
                if "证券" in str(col) and "代码" in str(col):
                    code_col = col
                    break
            if code_col:
                filtered = df[df[code_col].astype(str).str.contains(code)]
            else:
                filtered = df
            if filtered.empty:
                return f"{symbol} 在 {start_date}~{end_date} 无大宗交易记录。"
            return f"{symbol} 大宗交易明细（{start_date}~{end_date}）：\n{filtered.tail(10).to_string(index=False)}"
        except Exception as exc:
            return f"大宗交易数据获取失败：{type(exc).__name__}: {exc}"

    def get_lhb_institution_stats(self, symbol: str, start_date: str, end_date: str) -> str:
        """获取龙虎榜机构买卖统计。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            sd = start_date.replace("-", "")
            ed = end_date.replace("-", "")
            with AKSHARE_CALL_LOCK:
                df = ak.stock_lhb_jgmmtj_em(start_date=sd, end_date=ed)
            if df is None or df.empty:
                return f"{symbol} 在 {start_date}~{end_date} 无机构买卖统计数据。"
            code_col = None
            for col in df.columns:
                if "证券" in str(col) and "代码" in str(col):
                    code_col = col
                    break
            if code_col:
                filtered = df[df[code_col].astype(str).str.contains(code)]
            else:
                filtered = df
            if filtered.empty:
                return f"{symbol} 在 {start_date}~{end_date} 无机构买卖统计记录。"
            return f"{symbol} 龙虎榜机构买卖统计（{start_date}~{end_date}）：\n{filtered.to_string(index=False)}"
        except Exception as exc:
            return f"龙虎榜机构统计获取失败：{type(exc).__name__}: {exc}"

    def get_lhb_active_seats(self, start_date: str, end_date: str) -> str:
        """获取龙虎榜活跃营业部排行（市场级）。"""
        try:
            ak = self._ak()
            sd = start_date.replace("-", "")
            ed = end_date.replace("-", "")
            with AKSHARE_CALL_LOCK:
                df = ak.stock_lhb_hyyyb_em(start_date=sd, end_date=ed)
            if df is None or df.empty:
                return f"{start_date}~{end_date} 活跃营业部数据暂不可用。"
            return f"龙虎榜活跃营业部排行（{start_date}~{end_date}，前10）：\n{df.head(10).to_string(index=False)}"
        except Exception as exc:
            return f"龙虎榜活跃营业部获取失败：{type(exc).__name__}: {exc}"

    def get_research_reports(self, symbol: str) -> str:
        """获取个股机构研报列表（含评级和盈利预测）。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            with AKSHARE_CALL_LOCK:
                df = ak.stock_research_report_em(symbol=code)
            if df is None or df.empty:
                return f"{symbol} 机构研报数据暂不可用。"
            recent = df.head(5)
            return f"{symbol} 机构研报（最近5篇）：\n{recent.to_string(index=False)}"
        except Exception as exc:
            return f"机构研报数据获取失败：{type(exc).__name__}: {exc}"

    def get_shareholder_changes(self, symbol: str) -> str:
        """获取个股股东增减持记录。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            with AKSHARE_CALL_LOCK:
                df = ak.stock_shareholder_change_ths(symbol=code)
            if df is None or df.empty:
                return f"{symbol} 股东增减持数据暂不可用。"
            recent = df.head(5)
            return f"{symbol} 股东增减持记录（最近5条）：\n{recent.to_string(index=False)}"
        except Exception as exc:
            return f"股东增减持数据获取失败：{type(exc).__name__}: {exc}"

    def get_restricted_release(self, symbol: str) -> str:
        """获取个股限售解禁时间表。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            with AKSHARE_CALL_LOCK:
                df = ak.stock_restricted_release_queue_sina(symbol=code)
            if df is None or df.empty:
                return f"{symbol} 限售解禁数据暂不可用。"
            # 数据时效性检查：若解禁日期全部早于当年，视为过期
            date_col = None
            for col in df.columns:
                if "解禁" in str(col) and "日期" in str(col):
                    date_col = col
                    break
            if date_col is not None:
                latest = str(df[date_col].max())
                from datetime import datetime
                try:
                    latest_dt = datetime.strptime(latest[:10], "%Y-%m-%d")
                    if latest_dt.year < datetime.now().year:
                        return f"{symbol} 限售解禁数据已过期（最新解禁：{latest[:10]}），无近期数据。"
                except (ValueError, TypeError):
                    pass
            recent = df.head(5)
            return f"{symbol} 限售解禁计划（最近5批）：\n{recent.to_string(index=False)}"
        except Exception as exc:
            return f"限售解禁数据获取失败：{type(exc).__name__}: {exc}"

    def get_pledge_ratio(self, date: str) -> str:
        """获取全市场股权质押比率。"""
        try:
            ak = self._ak()
            date_str = date.replace("-", "")
            with AKSHARE_CALL_LOCK:
                result = ak.stock_gpzy_pledge_ratio_em(date=date_str)
            if result is None or (hasattr(result, 'empty') and result.empty):
                return f"{date} 股权质押数据暂不可用（非交易日或数据未更新）。"
            return f"全市场股权质押比率（{date}，前20高质押比例）：\n{result.head(20).to_string(index=False)}"
        except Exception:
            return f"{date} 股权质押数据暂不可用（非交易日或数据未更新）。"

    # ── Phase 2: 资金面/筹码/板块/公告（来自 a-stock-data SKILL） ──

    def get_shareholder_count(self, symbol: str) -> str:
        """获取股东户数变化（筹码集中度）。东财 datacenter RPT_HOLDERNUMLATEST。"""
        import json
        try:
            from .em_http_utils import eastmoney_datacenter
        except ImportError:
            return f"{symbol} 股东户数数据获取失败：em_http_utils 不可用。"
        code = self._normalize_symbol(symbol)
        try:
            rows = eastmoney_datacenter(
                report_name="RPT_HOLDERNUMLATEST",
                columns="ALL",
                filter_str=f'(SECURITY_CODE="{code}")',
                page_size=5,
                sort_columns="END_DATE",
                sort_types="-1",
            )
            if not rows:
                return f"{symbol} 股东户数数据暂不可用。"
            df = pd.DataFrame(rows)
            return f"{symbol} 股东户数变化（最近5期）：\n{df.head(5).to_string(index=False)}"
        except Exception as exc:
            return f"{symbol} 股东户数数据获取失败：{type(exc).__name__}: {exc}"

    def get_dividend_history(self, symbol: str) -> str:
        """获取分红送转历史（每股派息/送股/转增）。东财 datacenter RPT_SHAREBONUS_DET。"""
        code = self._normalize_symbol(symbol)
        try:
            from .em_http_utils import eastmoney_datacenter
            rows = eastmoney_datacenter(
                report_name="RPT_SHAREBONUS_DET",
                columns="ALL",
                filter_str=f'(SECURITY_CODE="{code}")',
                page_size=20,
                sort_columns="EQUITY_RECORD_DATE",
                sort_types="-1",
            )
            if not rows:
                return f"{symbol} 分红送转数据暂不可用。"
            df = pd.DataFrame(rows)
            return f"{symbol} 分红送转历史（最近20笔）：\n{df.to_string(index=False)}"
        except Exception as exc:
            return f"{symbol} 分红送转数据获取失败：{type(exc).__name__}: {exc}"

    def get_concept_board(self, symbol: str) -> str:
        """获取个股所属概念/行业/地域板块归属。东财 slist（spt=3），回退同花顺。"""
        code = self._normalize_symbol(symbol)
        market = "1" if code.startswith(("6", "9")) else "0"
        secid = f"{market}.{code}"
        try:
            from .em_http_utils import em_get
            url = "https://push2.eastmoney.com/api/qt/slist/get"
            params = {
                "spt": "3", "fltt": "2", "invt": "2",
                "fields": "f12,f14,f13,f3,f2,f15",
                "secids": secid,
            }
            r = em_get(url, params=params, timeout=10,
                       headers={"Referer": "https://quote.eastmoney.com/"})
            data = r.json()
            items = (data.get("data") or {}).get("diff")
            if items:
                result = []
                for it in items:
                    result.append({
                        "代码": it.get("f12", ""),
                        "板块名称": it.get("f14", ""),
                        "板块类型": it.get("f13", ""),
                        "涨跌幅%": it.get("f3", ""),
                        "最新价": it.get("f2", ""),
                    })
                df = pd.DataFrame(result)
                return f"{symbol} 所属板块归属：\n{df.to_string(index=False)}"
        except Exception:
            pass
        return self._concept_board_ths_fallback(symbol)

    def _concept_board_ths_fallback(self, symbol: str) -> str:
        """Fallback: use THS/xueqiu basic info for industry/concept data."""
        try:
            with AKSHARE_CALL_LOCK:
                ak = self._ak()
                df_info = ak.stock_individual_basic_info_xq(symbol=self._xq_symbol(symbol))
                if df_info is not None and not df_info.empty:
                    items = dict(zip(df_info["item"].astype(str), df_info["value"].astype(str)))
                    result = []
                    for key in ["行业", "板块", "概念", "上市板块"]:
                        if key in items:
                            result.append({"分类": key, "内容": items[key]})
                    if result:
                        df = pd.DataFrame(result)
                        return f"{symbol} 所属板块归属（同花顺）：\n{df.to_string(index=False)}"
        except Exception as exc:
            logger.debug("THS concept board fallback failed for %s: %s", symbol, exc)
        return f"{symbol} 概念板块数据暂不可用。"

    def get_individual_fund_flow_120d(self, symbol: str) -> str:
        """获取个股120日主力资金流向。东财 push2his daykline。"""
        code = self._normalize_symbol(symbol)
        market = "1" if code.startswith(("6", "9")) else "0"
        secid = f"{market}.{code}"
        try:
            from .em_http_utils import em_get
            url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
            params = {
                "lmt": "120", "klt": "101", "secid": secid,
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            }
            r = em_get(url, params=params, timeout=15,
                       headers={"Referer": "https://quote.eastmoney.com/"})
            data = r.json()
            if not data.get("data") or not data["data"].get("klines"):
                # Fallback: try akshare's built-in method
                return self._fund_flow_ak_fallback(symbol)
            klines = data["data"]["klines"]
            if not klines:
                return f"{symbol} 120日资金流向数据暂不可用。"
            rows = []
            for line in klines[-20:]:
                parts = line.split(",")
                if len(parts) >= 6:
                    rows.append({
                        "日期": parts[0],
                        "主力净流入(万)": self._safe_float(parts[1]),
                        "小单净流入(万)": self._safe_float(parts[2]),
                        "中单净流入(万)": self._safe_float(parts[3]),
                        "大单净流入(万)": self._safe_float(parts[4]),
                        "超大单净流入(万)": self._safe_float(parts[5]),
                    })
            if not rows:
                return f"{symbol} 120日资金流向数据暂不可用。"
            df = pd.DataFrame(rows)
            return f"{symbol} 资金流向（近20日）：\n{df.to_string(index=False)}"
        except Exception as exc:
            return self._fund_flow_ak_fallback(symbol)

    def _fund_flow_ak_fallback(self, symbol: str) -> str:
        """Fallback: use akshare stock_individual_fund_flow for fund flow data."""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            market = "sh" if code[:1] in ("5", "6", "9") else "sz"
            with AKSHARE_CALL_LOCK:
                df = ak.stock_individual_fund_flow(stock=code, market=market)
            if df is None or df.empty:
                return f"{symbol} 资金流向数据暂不可用。"
            recent = df.tail(20)
            return f"{symbol} 资金流向（近20日，akshare备选）：\n{recent.to_string(index=False)}"
        except Exception as exc:
            return f"{symbol} 资金流向数据获取失败：{type(exc).__name__}: {exc}"

    def get_cninfo_announcements(self, symbol: str, start_date: str, end_date: str) -> str:
        """获取个股巨潮公告全文检索。cninfo.com.cn（POST 接口）。"""
        import requests as _requests
        code = self._normalize_symbol(symbol)
        org_id = self._cninfo_orgid(code)
        # Determine exchange column: sse for SH, szse for SZ
        column = "sse" if code.startswith(("6", "9")) else "szse"
        try:
            url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
            form_data = {
                "pageNum": "1", "pageSize": "10",
                "column": column, "tabName": "fulltext",
                "plate": "", "stock": f"{code},{org_id}",
                "searchkey": "", "secid": "",
                "category": "", "trade": "",
                "seDate": f"{start_date}~{end_date}",
                "sortName": "date", "sortType": "desc",
            }
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
            }
            r = _requests.post(url, data=form_data, headers=headers, timeout=15)
            data = r.json()
            announcements = data.get("announcements") or []
            if not announcements:
                return f"{symbol} 在 {start_date}~{end_date} 无公告记录。"
            rows = []
            for ann in announcements[:10]:
                title = ann.get("announcementTitle", "无标题")
                ann_time = ann.get("announcementTime", "")
                if isinstance(ann_time, (int, float)):
                    from datetime import datetime as _dt
                    date_str = _dt.fromtimestamp(ann_time / 1000).strftime("%Y-%m-%d") if ann_time > 1e10 else str(ann_time)
                else:
                    date_str = str(ann_time)[:10]
                ann_id = ann.get("announcementId", "")
                sec_code = ann.get("secCode", "")
                url_link = f"https://static.cninfo.com.cn/{ann_id}"
                rows.append(f"- [{date_str}] {title} ({sec_code}) {url_link}")
            return f"{symbol} 巨潮公告（{start_date}~{end_date}，最近10条）：\n" + "\n".join(rows)
        except Exception as exc:
            return f"{symbol} 巨潮公告获取失败：{type(exc).__name__}: {exc}"

    # 巨潮 orgId 缓存（模块级，懒加载）
    _cninfo_org_map: dict[str, str] = {}

    def _cninfo_orgid(self, code: str) -> str:
        """Get cninfo orgId for a stock code. Uses dynamic lookup, falls back to heuristic."""
        if code in self._cninfo_org_map:
            return self._cninfo_org_map[code]
        try:
            org_map = self._cninfo_load_org_map()
            self._cninfo_org_map.update(org_map)
        except Exception:
            pass
        if code in self._cninfo_org_map:
            return self._cninfo_org_map[code]
        # Fallback heuristic: gssz0{code} for SZ, gssh0{code} for SH
        market_prefix = "gssz0" if code.startswith(("0", "2", "3")) else "gssh0"
        return f"{market_prefix}{code}"

    @staticmethod
    def _cninfo_load_org_map() -> dict[str, str]:
        """Load cninfo orgId mapping from official szse_stock.json."""
        import json as _json
        import requests as _requests
        url = "https://www.cninfo.com.cn/new/data/szse_stock.json"
        r = _requests.get(url, timeout=15,
                          headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.cninfo.com.cn/"})
        r.encoding = "utf-8"
        data = r.json()
        org_map = {}
        stock_list = data.get("stockList", data) if isinstance(data, dict) else data
        for item in stock_list:
            if not isinstance(item, dict):
                continue
            c = item.get("code", "")
            oid = item.get("orgId", "")
            if c and oid:
                org_map[c] = oid
        return org_map
