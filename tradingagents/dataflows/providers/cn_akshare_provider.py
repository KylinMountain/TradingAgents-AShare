import os
import re
import time
import threading
from datetime import datetime, timedelta

import pandas as pd
from stockstats import wrap

from .base import BaseMarketDataProvider
from ..trade_calendar import cn_market_phase, cn_no_data_reason, cn_today_str, is_cn_trading_day


AKSHARE_CALL_LOCK = threading.RLock()


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
        with AKSHARE_CALL_LOCK:
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
    def _shrink_table(df: pd.DataFrame, max_rows: int = 12, max_cols: int = 16) -> pd.DataFrame:
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
                        return self._maybe_append_realtime_row(symbol, out, end_date)
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
                        return self._maybe_append_realtime_row(symbol, out, end_date)
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
                    return self._maybe_append_realtime_row(symbol, out, end_date)
                except Exception as exc:
                    em_last_exc = exc
                    if i < 1:
                        time.sleep(0.6 * (i + 1))

            # Source 2: Sina
            try:
                df = ak.stock_zh_a_daily(
                    symbol=symbol_with_market,
                    start_date=start_yyyymmdd,
                    end_date=end_yyyymmdd,
                    adjust="qfq",
                )
                out = self._normalize_hist_df(df)
                return self._maybe_append_realtime_row(symbol, out, end_date)
            except Exception:
                pass

            # Source 3: Tencent
            try:
                df = ak.stock_zh_a_hist_tx(
                    symbol=symbol_with_market,
                    start_date=start_yyyymmdd,
                    end_date=end_yyyymmdd,
                    adjust="qfq",
                )
                out = self._normalize_hist_df(df)
                return self._maybe_append_realtime_row(symbol, out, end_date)
            except Exception:
                pass

            raise NotImplementedError(
                f"cn_akshare is temporarily unavailable for price history (eastmoney/sina/tencent all failed): {em_last_exc}"
            ) from em_last_exc

    def _fetch_realtime_row(self, symbol: str) -> pd.DataFrame:
        with AKSHARE_CALL_LOCK:
            ak = self._ak()
            xq_token = os.environ.get("XQ_A_TOKEN")
            spot = ak.stock_individual_spot_xq(symbol=self._xq_symbol(symbol), token=xq_token)
            if spot is None or spot.empty:
                return pd.DataFrame()
            if not {"item", "value"}.issubset(set(spot.columns)):
                return pd.DataFrame()
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
            return rt

    def _maybe_append_realtime_row(self, symbol: str, hist_df: pd.DataFrame, end_date: str) -> pd.DataFrame:
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

            rt = self._fetch_realtime_row(symbol)
            if rt.empty:
                return hist_df
            if pd.to_datetime(rt.iloc[0]["Date"]).normalize() != today:
                return hist_df

            merged = pd.concat([hist_df, rt], ignore_index=True)
            merged = merged.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
            return merged.reset_index(drop=True)
        except Exception:
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
                return self._shrink_table(df, max_rows=12, max_cols=18).to_markdown(index=False)
            except Exception as exc:
                errors.append(f"stock_financial_report_sina: {type(exc).__name__}")

            code = self._normalize_symbol(ticker)
            indicator = "按报告期"
            try:
                # 同花顺摘要表作为备用，口径不完全一致但可作为降级保障
                df = ak.stock_financial_abstract_new_ths(symbol=code, indicator=indicator)
                if df is None or df.empty:
                    raise ValueError("empty dataframe")
                return self._shrink_table(df, max_rows=12, max_cols=18).to_markdown(index=False)
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

    def get_global_news(self, curr_date: str) -> str:
        result = self.get_sina_global_news(page="1", page_size="100", tag_id="1,4,7")
        # get_sina_global_news 异常时返回 "新浪财经快讯获取失败：..." 字符串（truthy），需显式检查
        if result and result.startswith("## "):
            return result
        return f"{curr_date} 未获取到全球市场新闻"

    def get_insider_transactions(self, symbol: str) -> str:
        with AKSHARE_CALL_LOCK:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            errors = []
            try:
                # stock_ggcg_em 不支持按个股代码查询，默认全市场数据量较大
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

    def get_sina_global_news(
        self, page: str = "1", page_size: str = "20", zhibo_id: str = "152", tag_id: str = "0"
    ) -> str:
        """获取新浪财经全球快讯（支持参数）

        Args:
            page: 页码，默认 "1"
            page_size: 每页数量，默认 "20"
            zhibo_id: 直播ID，默认 "152"（财经）
            tag_id: 标签ID，默认 "0"（全部）

        Returns:
            格式化的新闻文本
        """
        with AKSHARE_CALL_LOCK:
            try:
                import requests
                import re as _re

                url = "https://zhibo.sina.com.cn/api/zhibo/feed"
                params = {
                    "page": page,
                    "page_size": page_size,
                    "zhibo_id": zhibo_id,
                    "tag_id": tag_id,
                    "dire": "f",
                    "dpc": "1",
                    "pagesize": page_size,
                    "type": "1",
                }

                r = requests.get(url, params=params, timeout=10)
                data_json = r.json()

                time_list = [
                    item["create_time"] for item in data_json["result"]["data"]["feed"]["list"]
                ]
                text_list = [
                    item["rich_text"] for item in data_json["result"]["data"]["feed"]["list"]
                ]

                if not text_list:
                    return "未获取到新浪财经快讯"

                rows = []
                for time_str, content in zip(time_list, text_list):
                    if not content or content == "nan":
                        continue
                    m = _re.match(r"^【(.+?)】(.*)", content, _re.DOTALL)
                    if m:
                        title, body = m.group(1), m.group(2).strip()
                        rows.append(f"### [{time_str}] {title}")
                        if body:
                            rows.append(body[:300])
                        rows.append("")

                # 每条新闻占3行（标题、正文可选、空行），计算实际输出的新闻数
                actual_count = len([r for r in rows if r.startswith("###")])
                return f"## 新浪财经快讯（第{page}页，共{actual_count}条）：\n\n" + "\n".join(rows)

            except Exception as exc:
                return f"新浪财经快讯获取失败：{type(exc).__name__}: {exc}"

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
            with AKSHARE_CALL_LOCK:
                ak = self._ak()
                df = ak.stock_zh_a_spot_em()
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
        except Exception:
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
                    "volume": self._safe_float(fields[8]),
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
        """获取行业板块资金流向排名。

        注意：此接口依赖 akshare，可能因东方财富 API 变化而暂时不可用。
        """
        try:
            ak = self._ak()
            # 使用正确的方法名 stock_fund_flow_industry
            df = ak.stock_fund_flow_industry(symbol="即时")
            if df is None or df.empty:
                return "今日板块资金流向数据暂不可用。"
            sort_col = "今日主力净流入-净额"
            if sort_col in df.columns:
                df_sorted = df.sort_values(sort_col, ascending=False).reset_index(drop=True)
            else:
                df_sorted = df.reset_index(drop=True)
            df_sorted.insert(0, "排名", range(1, len(df_sorted) + 1))
            total = len(df_sorted)
            result = df_sorted.head(10).to_string(index=False)
            return f"板块资金流向排名（共{total}个板块，前10名）：\n{result}"
        except Exception as exc:
            return f"板块资金流向数据暂时不可用（akshare 接口问题）：{type(exc).__name__}"

    def get_individual_fund_flow(self, symbol: str) -> str:
        """获取个股近期主力资金净流向。"""
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            # 沪市：以 5、6、9 开头；其余为深市
            market = "sh" if code[:1] in ("5", "6", "9") else "sz"
            df = ak.stock_individual_fund_flow(stock=code, market=market)
            if df is None or df.empty:
                return f"{symbol} 近期主力资金流向数据暂不可用。"
            df_recent = df.tail(5)
            return f"{symbol} 近5日主力资金净流向：\n{df_recent.to_string(index=False)}"
        except Exception as exc:
            return f"个股资金流向数据获取失败：{type(exc).__name__}: {exc}"

    def get_lhb_detail(self, symbol: str, date: str) -> str:
        """获取龙虎榜数据，非异动日返回空提示（属正常）。

        注意：此接口依赖 akshare，可能因东方财富 API 变化而暂时不可用。
        """
        try:
            ak = self._ak()
            code = self._normalize_symbol(symbol)
            # stock_lhb_detail_em 不接受 symbol 参数，返回全市场数据
            date_fmt = date.replace("-", "")
            df = ak.stock_lhb_detail_em(start_date=date_fmt, end_date=date_fmt)
            if df is None or df.empty:
                return f"{date} 全市场无龙虎榜数据。"
            # 手动过滤指定股票
            if "代码" in df.columns:
                df = df[df["代码"] == code]
            if df.empty:
                return f"{symbol} 在 {date} 无龙虎榜数据（非异动日属正常）。"
            return f"{symbol} 龙虎榜明细（{date}）：\n{df.head(20).to_string(index=False)}"
        except TypeError as exc:
            # akshare 当日数据未更新时，data_json["result"] 为 None
            return f"{date} 龙虎榜数据尚未更新（通常发生在盘中查询当日数据）。"
        except Exception as exc:
            return f"龙虎榜数据获取失败（akshare 接口异常）：{type(exc).__name__}"

    def get_zt_pool(self, date: str) -> str:
        """获取涨停板情绪池，反映市场整体情绪温度。"""
        try:
            ak = self._ak()
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
            df = ak.stock_hot_follow_xq(symbol="本周新增")
            if df is None or df.empty:
                return "雪球热搜数据暂不可用。"
            return f"雪球热搜前20：\n{df.head(20).to_string(index=False)}"
        except Exception as exc:
            return f"雪球热搜数据获取失败：{type(exc).__name__}: {exc}"
