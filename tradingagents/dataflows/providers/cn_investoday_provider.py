"""A-share market data via 今日投资 (Investoday) REST API — 行情、新闻、前复权 K 线、财报与高管持股等。"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests
from stockstats import wrap

from .base import BaseMarketDataProvider
from ..config import get_config
from ..trade_calendar import cn_no_data_reason

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://data-api.investoday.net/data"
_REALTIME_PATH = "/stock-quote/realtime"
_NEWS_PATH = "/news"
_NEWS_ENTITY_PATH = "/news/entity-related"
_ADJUSTED_QUOTES_PATH = "/stock/adjusted-quotes"
_COMPANY_PROFILES_PATH = "/stock/company/profiles"
_BALANCE_SHEETS_PATH = "/stock/balance-sheets"
_BALANCE_SHEETS_Q_PATH = "/stock/balance-sheets-q"
_INCOME_STATEMENTS_PATH = "/stock/income-statements"
_INCOME_STATEMENTS_Q_PATH = "/stock/income-statements-q"
_CASH_FLOWS_PATH = "/stock/cash-flows"
_CASH_FLOWS_Q_PATH = "/stock/cash-flows-q"
_EXEC_SHRHLD_CHG_PATH = "/stock/exec-shrhld-chg"

_MAX_PAGES = 80
_PAGE_SIZE = 500


class CnInvestodayProvider(BaseMarketDataProvider):
    """今日投资：实时行情、前复权日 K、技术指标（stockstats）、公司信息、三大报表、新闻、高管持股变动。"""

    INDICATOR_DESCRIPTIONS = {
        "close_50_sma": "50 日均线（SMA）：中期趋势指标。",
        "close_200_sma": "200 日均线（SMA）：长期趋势基准。",
        "close_10_ema": "10 日指数均线（EMA）：短期响应更快。",
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
        """在路由与配置中使用的数据源标识。"""
        return "cn_investoday"

    def _resolve_api_key(self) -> str:
        """读取今日投资 API Key：配置 investoday_api_key，其次环境变量 INVESTODAY_API_KEY。"""
        config = get_config()
        return (
            str(config.get("investoday_api_key", "")).strip()
            or os.getenv("INVESTODAY_API_KEY", "").strip()
        )

    def _require_api_key(self) -> str:
        key = self._resolve_api_key()
        if not key:
            raise NotImplementedError(
                "cn_investoday 需要 API Key。请在配置中设置 investoday_api_key "
                "或环境变量 INVESTODAY_API_KEY。"
            )
        return key

    def _resolve_base_url(self) -> str:
        """REST 根路径：配置 investoday_base_url / 环境 INVESTODAY_BASE_URL，缺省为官方 data 前缀。"""
        config = get_config()
        base = (
            str(config.get("investoday_base_url", "")).strip()
            or os.getenv("INVESTODAY_BASE_URL", "").strip()
            or _DEFAULT_BASE_URL
        )
        return base.rstrip("/")

    @staticmethod
    def _normalize_stock_code(symbol: str) -> str | None:
        """从任意写法中提取 6 位证券代码；无法识别则返回 None。"""
        s = symbol.strip()
        m = re.search(r"(\d{6})", s)
        return m.group(1) if m else None

    @staticmethod
    def _safe_float(val: Any) -> float | None:
        """将接口返回值安全转为 float，失败或空为 None。"""
        if val is None:
            return None
        try:
            f = float(val)
            return f
        except (ValueError, TypeError):
            return None

    def _request_investoday(
        self,
        path: str,
        params: dict[str, Any],
        api_key: str,
        base_url: str,
    ) -> dict[str, Any] | None:
        """发起 GET 请求并校验 ``code==0``；失败返回 None。"""
        url = f"{base_url}{path}"
        try:
            resp = requests.get(
                url,
                params={k: v for k, v in params.items() if v is not None},
                headers={"apiKey": api_key},
                timeout=20,
            )
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, OSError, ValueError) as exc:
            logger.debug("[cn_investoday] GET %s failed: %s", path, exc)
            return None
        if not isinstance(payload, dict):
            return None
        if int(payload.get("code", -1)) != 0:
            logger.debug(
                "[cn_investoday] GET %s code=%s msg=%s",
                path,
                payload.get("code"),
                payload.get("message"),
            )
            return None
        return payload

    def _fetch_paged_list(
        self,
        path: str,
        params_base: dict[str, Any],
        api_key: str,
        base_url: str,
    ) -> list[dict[str, Any]]:
        """按 ``pageNum``/``pageSize`` 拉取列表类接口，直到单页不足 ``pageSize`` 或达上限。"""
        out: list[dict[str, Any]] = []
        page = 1
        while page <= _MAX_PAGES:
            params = {**params_base, "pageNum": page, "pageSize": _PAGE_SIZE}
            payload = self._request_investoday(path, params, api_key, base_url)
            if payload is None:
                break
            data = payload.get("data")
            if not isinstance(data, list) or not data:
                break
            for item in data:
                if isinstance(item, dict):
                    out.append(item)
            if len(data) < _PAGE_SIZE:
                break
            page += 1
        return out

    def _iv_adjusted_rows_to_df(self, rows: list[dict[str, Any]]) -> pd.DataFrame:
        """将前复权日行情 JSON 行转为标准 OHLCV DataFrame。"""
        recs: list[dict[str, Any]] = []
        for r in rows:
            recs.append(
                {
                    "Date": r.get("date"),
                    "Open": self._safe_float(r.get("openPrice")),
                    "High": self._safe_float(r.get("highPrice")),
                    "Low": self._safe_float(r.get("lowPrice")),
                    "Close": self._safe_float(r.get("closePrice")),
                    "Volume": self._safe_float(r.get("volume")),
                }
            )
        df = pd.DataFrame(recs)
        if df.empty:
            return df
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for c in ("Open", "High", "Low", "Close", "Volume"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"])
        df["Volume"] = df["Volume"].astype(float)
        return df.sort_values("Date").reset_index(drop=True)

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

    def _format_hist_csv(self, df: pd.DataFrame, symbol: str, start: str, end: str) -> str:
        """与 AkShare  provider 一致的 CSV 头 + OHLCV 输出。"""
        if df is None or df.empty:
            return f"No data found for symbol '{symbol}' between {start} and {end}"
        out = df.copy()
        out["Dividends"] = 0.0
        out["Stock Splits"] = 0.0
        out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")
        header = f"# Stock data for {symbol} from {start} to {end}\n"
        header += f"# Total records: {len(out)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + out.to_csv(index=False)

    def _fetch_adjusted_hist_df(
        self, symbol: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """前复权日行情合并分页后的 DataFrame。"""
        api_key = self._require_api_key()
        code = self._normalize_stock_code(symbol)
        if not code:
            return pd.DataFrame()
        base_url = self._resolve_base_url()
        rows = self._fetch_paged_list(
            _ADJUSTED_QUOTES_PATH,
            {"stockCode": code, "beginDate": start_date, "endDate": end_date},
            api_key,
            base_url,
        )
        return self._iv_adjusted_rows_to_df(rows)

    def _fetch_one_realtime(self, stock_code: str, api_key: str, base_url: str) -> dict[str, Any] | None:
        """单股实时日行情。"""
        payload = self._request_investoday(
            _REALTIME_PATH, {"stockCode": stock_code}, api_key, base_url
        )
        if not payload:
            return None
        data = payload.get("data")
        if not isinstance(data, dict):
            return None

        price = self._safe_float(data.get("currentPrice"))
        prev = self._safe_float(data.get("closePriceYDay"))
        change = None
        if price is not None and prev is not None:
            change = round(price - prev, 4)

        ratio = self._safe_float(data.get("changeRatio"))
        change_pct = round(ratio * 100, 4) if ratio is not None else None

        quote_time = data.get("dataTime")
        if quote_time is not None:
            quote_time = str(quote_time).strip() or None

        return {
            "price": price,
            "open": self._safe_float(data.get("openPrice")),
            "high": self._safe_float(data.get("highPrice")),
            "low": self._safe_float(data.get("lowPrice")),
            "previous_close": prev,
            "change": change,
            "change_pct": change_pct,
            "volume": self._safe_float(data.get("dealStockAmount")),
            "amount": self._safe_float(data.get("dealMoney")),
            "quote_time": quote_time,
            "source": "investoday",
        }

    def get_realtime_quotes(self, symbols: list[str]) -> str:
        """批量拉取实时行情；返回 JSON 字符串。"""
        api_key = self._require_api_key()

        code_to_original: dict[str, str] = {}
        for s in symbols:
            if not s or not str(s).strip():
                continue
            code = self._normalize_stock_code(str(s))
            if not code:
                continue
            if code not in code_to_original:
                code_to_original[code] = str(s).strip().upper()

        if not code_to_original:
            return json.dumps({})

        base_url = self._resolve_base_url()
        result: dict[str, dict[str, Any]] = {}
        for stock_code, original in code_to_original.items():
            row = self._fetch_one_realtime(stock_code, api_key, base_url)
            if row is not None:
                result[original] = row

        if not result:
            raise NotImplementedError(
                "cn_investoday 未获取到任何实时行情（请检查 stockCode、额度与网络）。"
            )

        return json.dumps(result, ensure_ascii=False)

    @staticmethod
    def _parse_news_datetime(val: Any) -> datetime | None:
        if val is None:
            return None
        s = str(val).strip()
        if not s:
            return None
        try:
            if len(s) >= 19 and s[10] == " ":
                return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None

    def _format_news_item(self, item: dict[str, Any]) -> list[str]:
        title = str(item.get("title", "No title")).strip() or "No title"
        rows_out: list[str] = [f"### {title} (source: 今日投资)"]
        summary = str(item.get("summary", "")).strip()
        if summary and summary != "nan":
            rows_out.append(summary[:400])
        kp = str(item.get("keyPoints", "")).strip()
        if kp and kp != "nan":
            rows_out.append(f"要点: {kp[:220]}")
        impact = str(item.get("impactAnalysis", "")).strip()
        if impact and impact != "nan":
            rows_out.append(f"影响分析: {impact[:220]}")
        nid = str(item.get("newsId", "")).strip()
        if nid:
            rows_out.append(f"newsId: {nid}")
        rows_out.append("")
        return rows_out

    def _news_rows_in_range(
        self,
        rows: list[Any],
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        out: list[dict[str, Any]] = []
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            dt = self._parse_news_datetime(raw.get("date"))
            if dt is None:
                out.append(raw)
                continue
            if start_dt <= dt < end_dt:
                out.append(raw)
        return out

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        """个股相关新闻：``GET /news/entity-related``。"""
        api_key = self._require_api_key()
        code = self._normalize_stock_code(ticker)
        if not code:
            return f"No news found for {ticker} (无法解析证券代码)"

        base_url = self._resolve_base_url()
        params: dict[str, Any] = {
            "stockCode": code,
            "beginTime": f"{start_date} 00:00:00",
            "endTime": f"{end_date} 23:59:59",
            "pageNum": 1,
            "pageSize": min(50, 500),
        }
        payload = self._request_investoday(_NEWS_ENTITY_PATH, params, api_key, base_url)
        if payload is None:
            raise NotImplementedError(
                "cn_investoday 新闻接口请求失败（网络或返回码异常），请稍后重试或换用其它数据源。"
            )
        data = payload.get("data")
        if not isinstance(data, list):
            raise NotImplementedError(
                "cn_investoday 新闻接口返回格式异常（data 非列表），请换用其它数据源。"
            )
        filtered = self._news_rows_in_range(data, start_date, end_date)
        if not filtered:
            return f"No news found for {ticker} between {start_date} and {end_date}"

        parts: list[str] = [f"## {ticker} 新闻（{start_date} 至 {end_date}）：\n"]
        for item in filtered[:20]:
            parts.extend(self._format_news_item(item))
        return "\n".join(parts).rstrip() + "\n"

    def get_global_news(
        self, curr_date: str, look_back_days: int = 7, limit: int = 50
    ) -> str:
        """全市场新闻：优先宏观 ``newsType=1``，空则去掉类型重试。"""
        api_key = self._require_api_key()
        end_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=look_back_days)
        begin_time = start_dt.strftime("%Y-%m-%d 00:00:00")
        end_time = f"{curr_date} 23:59:59"
        page_size = min(max(limit, 1), 500)

        base_url = self._resolve_base_url()
        params_macro: dict[str, Any] = {
            "beginTime": begin_time,
            "endTime": end_time,
            "newsType": 1,
            "pageNum": 1,
            "pageSize": page_size,
        }
        payload = self._request_investoday(_NEWS_PATH, params_macro, api_key, base_url)
        rows: list[Any] = []
        if payload is not None:
            data = payload.get("data")
            if isinstance(data, list):
                rows = data

        if not rows:
            params_broad: dict[str, Any] = {
                "beginTime": begin_time,
                "endTime": end_time,
                "pageNum": 1,
                "pageSize": page_size,
            }
            payload2 = self._request_investoday(_NEWS_PATH, params_broad, api_key, base_url)
            if payload2 is None:
                raise NotImplementedError(
                    "cn_investoday 全市场新闻请求失败（网络或返回码异常），请稍后重试或换用其它数据源。"
                )
            data2 = payload2.get("data")
            if not isinstance(data2, list):
                raise NotImplementedError(
                    "cn_investoday 全市场新闻返回格式异常（data 非列表），请换用其它数据源。"
                )
            rows = data2

        start_label = start_dt.strftime("%Y-%m-%d")
        if not rows:
            return f"{curr_date} 未获取到全球市场新闻（{start_label} 至 {curr_date}）"

        parts: list[str] = [f"## 全球市场新闻（{start_label} 至 {curr_date}）：\n"]
        for item in rows[:limit]:
            if isinstance(item, dict):
                parts.extend(self._format_news_item(item))
        return "\n".join(parts).rstrip() + "\n"

    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str:
        """前复权日 K 线：``GET /stock/adjusted-quotes``（分页），输出 CSV 与 AkShare 一致。"""
        self._require_api_key()
        df = self._fetch_adjusted_hist_df(symbol, start_date, end_date)
        df = self._slice_hist_df(df, start_date, end_date)
        return self._format_hist_csv(df, symbol, start_date, end_date)

    def get_indicators(
        self, symbol: str, indicator: str, curr_date: str, look_back_days: int
    ) -> str:
        """基于前复权 OHLCV + stockstats，与 ``cn_akshare`` 指标名及输出格式对齐。"""
        if indicator not in self.INDICATOR_DESCRIPTIONS:
            raise ValueError(
                f"Indicator {indicator} is not supported. "
                f"Please choose from: {list(self.INDICATOR_DESCRIPTIONS.keys())}"
            )
        self._require_api_key()
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = curr_dt - timedelta(days=max(look_back_days, 260))
        df = self._fetch_adjusted_hist_df(
            symbol, start_dt.strftime("%Y-%m-%d"), curr_date
        )
        df = self._slice_hist_df(df, start_dt.strftime("%Y-%m-%d"), curr_date)
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

        values_by_date: dict[str, str] = {}
        for idx, dt_val in enumerate(ind_df["date"]):
            date_str = pd.to_datetime(dt_val).strftime("%Y-%m-%d")
            val = indicator_series.iloc[idx]
            values_by_date[date_str] = "N/A" if pd.isna(val) else str(val)

        begin = curr_dt - timedelta(days=look_back_days)
        lines: list[str] = []
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
        """公司基本信息：``GET /stock/company/profiles``。"""
        api_key = self._require_api_key()
        code = self._normalize_stock_code(ticker)
        if not code:
            raise NotImplementedError(f"cn_investoday 无法解析证券代码: {ticker}")

        base_url = self._resolve_base_url()
        payload = self._request_investoday(
            _COMPANY_PROFILES_PATH, {"stockCode": code}, api_key, base_url
        )
        if payload is None:
            raise NotImplementedError(
                "cn_investoday 公司信息接口请求失败，请换用其它数据源。"
            )
        data = payload.get("data")
        if not isinstance(data, list) or not data:
            return f"## Fundamentals for {ticker}\n\n未获取到公司基本信息。"
        row = data[0]
        if not isinstance(row, dict):
            return f"## Fundamentals for {ticker}\n\n未获取到公司基本信息。"
        df = pd.DataFrame([{k: str(v)[:500] for k, v in row.items()}])
        table = self._shrink_table(df, max_rows=2, max_cols=24).to_string(index=False)
        return f"## Fundamentals for {ticker}（今日投资 company/profiles）\n\n{table}"

    @staticmethod
    def _shrink_table(df: pd.DataFrame, max_rows: int = 12, max_cols: int = 16) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        rows = min(max_rows, len(df))
        cols = min(max_cols, len(df.columns))
        return df.head(rows).iloc[:, :cols]

    @staticmethod
    def _is_quarterly_freq(freq: str) -> bool:
        f = (freq or "").strip().lower()
        return f in ("quarterly", "quarter", "q")

    def _financial_path(self, kind: str, freq: str) -> str:
        q = self._is_quarterly_freq(freq)
        if kind == "balance":
            return _BALANCE_SHEETS_Q_PATH if q else _BALANCE_SHEETS_PATH
        if kind == "income":
            return _INCOME_STATEMENTS_Q_PATH if q else _INCOME_STATEMENTS_PATH
        if kind == "cashflow":
            return _CASH_FLOWS_Q_PATH if q else _CASH_FLOWS_PATH
        raise ValueError(f"unknown financial kind: {kind}")

    def _financial_report_markdown(
        self,
        kind: str,
        title_cn: str,
        ticker: str,
        freq: str,
        curr_date: str | None,
    ) -> str:
        """三大报表：Query 为 ``stockCode`` + ``beginDate``/``endDate``（与官方文档一致）。"""
        api_key = self._require_api_key()
        code = self._normalize_stock_code(ticker)
        if not code:
            raise NotImplementedError(f"cn_investoday 无法解析证券代码: {ticker}")

        end_d = curr_date or datetime.now().strftime("%Y-%m-%d")
        begin_d = (datetime.strptime(end_d, "%Y-%m-%d") - timedelta(days=365 * 8)).strftime(
            "%Y-%m-%d"
        )
        path = self._financial_path(kind, freq)
        base_url = self._resolve_base_url()
        rows = self._fetch_paged_list(
            path,
            {"stockCode": code, "beginDate": begin_d, "endDate": end_d},
            api_key,
            base_url,
        )
        if not rows:
            return f"## {title_cn} ({ticker})\n\n未获取到报表数据（今日投资 {path}）。"
        df = pd.DataFrame(rows)
        table = self._shrink_table(df, max_rows=12, max_cols=18).to_string(index=False)
        freq_note = "单季度" if self._is_quarterly_freq(freq) else "合并/报告期口径以接口为准"
        return (
            f"## {title_cn} ({ticker}) — 今日投资 {path}（{freq_note}）\n\n{table}"
        )

    def get_balance_sheet(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return self._financial_report_markdown("balance", "资产负债表", ticker, freq, curr_date)

    def get_cashflow(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return self._financial_report_markdown("cashflow", "现金流量表", ticker, freq, curr_date)

    def get_income_statement(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        return self._financial_report_markdown("income", "利润表", ticker, freq, curr_date)

    def get_insider_transactions(self, symbol: str) -> str:
        """高管持股变动：``GET /stock/exec-shrhld-chg``（口径异于全市场股东增减持）。"""
        api_key = self._require_api_key()
        code = self._normalize_stock_code(symbol)
        if not code:
            raise NotImplementedError(f"cn_investoday 无法解析证券代码: {symbol}")

        end_d = datetime.now().strftime("%Y-%m-%d")
        begin_d = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
        base_url = self._resolve_base_url()
        rows = self._fetch_paged_list(
            _EXEC_SHRHLD_CHG_PATH,
            {"stockCode": code, "beginDate": begin_d, "endDate": end_d},
            api_key,
            base_url,
        )
        if not rows:
            return (
                f"## Insider / 高管持股变动 for {symbol}\n\n"
                "未获取到数据（今日投资 exec-shrhld-chg）。\n"
                "说明：本接口为「高管持股变动明细」，不等同全量股东增减持或大宗交易。"
            )
        df = pd.DataFrame(rows)
        table = self._shrink_table(df, max_rows=25, max_cols=14).to_string(index=False)
        return (
            f"## Insider Transactions for {symbol}\n\n"
            "数据来源：今日投资「高管持股变动明细」`/stock/exec-shrhld-chg`，"
            "仅含高管/关联人持股变动，不等同全体股东增减持。\n\n"
            f"{table}"
        )
