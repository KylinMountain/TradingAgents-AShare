import logging as _logging
import re
from datetime import datetime, timedelta

import pandas as pd

from .base import BaseMarketDataProvider

logger = _logging.getLogger(__name__)

# ── mootdx 全局客户端 ──
# Quotes.factory 内部自带连接池，单例复用即可，无需每次创建
_mootdx_client = None


def _get_client():
    global _mootdx_client
    if _mootdx_client is None:
        try:
            from mootdx.quotes import Quotes
        except ImportError:
            raise NotImplementedError(
                "cn_mootdx requires 'mootdx'. Install it with: pip install mootdx"
            )
        _mootdx_client = Quotes.factory(market="std")
    return _mootdx_client


class CnMootdxProvider(BaseMarketDataProvider):
    """A-share provider backed by mootdx (通达信 TCP 行情).

    优势：TCP 直连通达信服务器(7709)，不封 IP，适合高频调用。
    提供：K 线、实时盘口、逐笔成交、财务快照、F10 公司资料。
    不提供：新闻、公告、技术指标（回退到 akshare）。
    """

    @property
    def name(self) -> str:
        return "cn_mootdx"

    # ── 工具方法 ──

    def _normalize_symbol(self, symbol: str) -> str:
        s = symbol.strip().lower()
        m = re.search(r"(\d{6})", s)
        if not m:
            raise NotImplementedError(
                f"cn_mootdx only supports A-share 6-digit symbols, got: {symbol}"
            )
        return m.group(1)

    def _market_code(self, symbol: str) -> int:
        """mootdx market: 0=深圳, 1=上海"""
        code = self._normalize_symbol(symbol)
        return 0 if code.startswith(("0", "2", "3", "4", "8")) else 1

    def _normalize_hist_df(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        if raw_df is None or raw_df.empty:
            return pd.DataFrame()

        df = raw_df.copy()

        # mootdx bars: datetime index + columns [open, close, high, low, vol, volume, amount, datetime, ...]
        # Normalize: use datetime index if available, otherwise datetime column
        if isinstance(df.index, pd.DatetimeIndex):
            df["Date"] = df.index
        elif "datetime" in df.columns:
            df["Date"] = pd.to_datetime(df["datetime"], errors="coerce")

        # Map columns, preferring 'volume' over 'vol' (mootdx has both)
        col_map = {
            "open": "Open", "high": "High", "low": "Low", "close": "Close",
        }
        df = df.rename(columns=col_map)
        # Use 'volume' column if present, else fallback to 'vol'
        if "volume" in df.columns:
            df["Volume"] = pd.to_numeric(df["volume"], errors="coerce")
        elif "vol" in df.columns:
            df["Volume"] = pd.to_numeric(df["vol"], errors="coerce")

        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"mootdx hist dataframe missing columns: {missing}")

        out = df[required].copy()
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
        out = out.dropna(subset=["Date"]).sort_values("Date")

        for c in ["Open", "High", "Low", "Close", "Volume"]:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        out["Volume"] = out["Volume"].astype(float)

        return out

    def _format_hist_csv(self, df: pd.DataFrame, symbol: str, start: str, end: str) -> str:
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
    def _safe_float(val) -> float | None:
        if val is None:
            return None
        try:
            f = float(val)
            return f if not pd.isna(f) else None
        except (ValueError, TypeError):
            return None

    # ── 基类方法实现 ──

    def get_stock_data(self, symbol: str, start_date: str, end_date: str) -> str:
        """通过 mootdx TCP 获取日 K 线，不封 IP。"""
        client = _get_client()
        code = self._normalize_symbol(symbol)
        market = self._market_code(symbol)

        try:
            # mootdx bars: category=4=日线, offset 取足够多确保覆盖起止日期
            # 实际偏移量 = 获取最近 N 根 K 线
            bars = client.bars(symbol=code, category=4, offset=400)
        except Exception as exc:
            raise NotImplementedError(
                f"cn_mootdx failed to fetch K-line for {symbol}: {exc}"
            ) from exc

        if bars is None or bars.empty:
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

        fmt = self._normalize_hist_df(bars)
        if fmt.empty:
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

        # 日期过滤
        start_dt = pd.to_datetime(start_date, errors="coerce")
        end_dt = pd.to_datetime(end_date, errors="coerce")
        if not pd.isna(start_dt) and not pd.isna(end_dt):
            fmt = fmt[(fmt["Date"] >= start_dt) & (fmt["Date"] <= end_dt)]

        return self._format_hist_csv(fmt, symbol, start_date, end_date)

    def get_indicators(
        self, symbol: str, indicator: str, curr_date: str, look_back_days: int
    ) -> str:
        raise NotImplementedError("cn_mootdx doesn't compute indicators; fallback to cn_akshare")

    # 37 字段中文标签映射
    FINANCE_LABELS = {
        "market": "市场", "code": "代码", "liutongguben": "流通股本",
        "province": "省份", "industry": "行业", "updated_date": "更新日期",
        "ipo_date": "上市日期", "zongguben": "总股本", "guojiagu": "国家股",
        "faqirenfarengu": "发起人法人股", "farengu": "法人股", "bgu": "B股",
        "hgu": "H股", "zhigonggu": "职工股", "zongzichan": "总资产",
        "liudongzichan": "流动资产", "gudingzichan": "固定资产",
        "wuxingzichan": "无形资产", "gudongrenshu": "股东人数",
        "liudongfuzhai": "流动负债", "changqifuzhai": "长期负债",
        "zibengongjijin": "资本公积金", "jingzichan": "净资产",
        "zhuyingshouru": "主营业务收入", "zhuyinglirun": "主营业务利润",
        "yingshouzhangkuan": "应收账款", "yingyelirun": "营业利润",
        "touzishouyu": "投资收益", "jingyingxianjinliu": "经营现金流",
        "zongxianjinliu": "总现金流", "cunhuo": "存货",
        "lirunzonghe": "利润总额", "shuihoulirun": "税后利润",
        "jinglirun": "净利润", "weifenpeilirun": "未分配利润",
        "meigujingzichan": "每股净资产", "baoliu2": "保留字段2",
    }

    def get_fundamentals(self, ticker: str, curr_date: str = None) -> str:
        """通过 mootdx finance 获取财务快照（37 字段：EPS/ROE/净利等）。"""
        client = _get_client()
        code = self._normalize_symbol(ticker)

        try:
            fin = client.finance(symbol=code)
        except Exception as exc:
            raise NotImplementedError(
                f"cn_mootdx failed to fetch fundamentals for {ticker}: {exc}"
            ) from exc

        if fin is None or (hasattr(fin, "empty") and fin.empty):
            raise NotImplementedError(
                f"cn_mootdx returned empty fundamentals for {ticker}"
            )

        # finance() returns DataFrame with 1 row, 37 columns
        row = fin.iloc[0] if hasattr(fin, "iloc") else fin
        rows = []
        for col in fin.columns:
            val = row.get(col) if isinstance(row, dict) else row[col]
            if val is not None and str(val) != "nan":
                label = self.FINANCE_LABELS.get(str(col), str(col))
                rows.append({"指标": label, "数值": val})

        if not rows:
            raise NotImplementedError(
                f"cn_mootdx returned empty fundamentals for {ticker}"
            )

        df_out = pd.DataFrame(rows)
        return f"## Fundamentals for {ticker} (mootdx 财务快照)\n\n{df_out.to_markdown(index=False)}"

    def get_balance_sheet(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        raise NotImplementedError(
            "cn_mootdx doesn't provide full balance sheet; fallback to cn_akshare"
        )

    def get_cashflow(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        raise NotImplementedError(
            "cn_mootdx doesn't provide full cashflow statement; fallback to cn_akshare"
        )

    def get_income_statement(
        self, ticker: str, freq: str = "quarterly", curr_date: str = None
    ) -> str:
        raise NotImplementedError(
            "cn_mootdx doesn't provide full income statement; fallback to cn_akshare"
        )

    def get_news(self, ticker: str, start_date: str, end_date: str) -> str:
        raise NotImplementedError("cn_mootdx doesn't provide news; fallback to cn_akshare")

    def get_global_news(
        self, curr_date: str, look_back_days: int = 7, limit: int = 50
    ) -> str:
        raise NotImplementedError("cn_mootdx doesn't provide global news; fallback to cn_akshare")

    def get_insider_transactions(self, symbol: str) -> str:
        raise NotImplementedError(
            "cn_mootdx doesn't provide insider transactions; fallback to cn_akshare"
        )

    def get_realtime_quotes(self, symbols: list[str]) -> str:
        """通过 mootdx 获取实时五档盘口报价。"""
        import json

        client = _get_client()
        codes = []
        original_map: dict[str, str] = {}
        for s in symbols:
            if not s or not s.strip():
                continue
            try:
                code = self._normalize_symbol(s)
            except NotImplementedError:
                continue
            if code:
                codes.append(code)
                original_map[code] = s.strip().upper()

        if not codes:
            return json.dumps({})

        try:
            quotes_df = client.quotes(symbol=codes)
        except Exception as exc:
            raise NotImplementedError(
                f"cn_mootdx failed to fetch realtime quotes: {exc}"
            ) from exc

        if quotes_df is None or (hasattr(quotes_df, "empty") and quotes_df.empty):
            return json.dumps({})

        result: dict[str, dict] = {}
        for _, q in quotes_df.iterrows():
            code = str(q.get("code", "")).strip()
            original = original_map.get(code)
            if not original:
                continue
            price = self._safe_float(q.get("price"))
            prev_close = self._safe_float(q.get("last_close"))
            change = round(price - prev_close, 4) if price is not None and prev_close else None
            change_pct = round(change / prev_close * 100, 4) if change is not None and prev_close else None
            result[original] = {
                "price": price,
                "open": self._safe_float(q.get("open")),
                "high": self._safe_float(q.get("high")),
                "low": self._safe_float(q.get("low")),
                "previous_close": prev_close,
                "change": change,
                "change_pct": change_pct,
                "volume": self._safe_float(q.get("vol")),
                "amount": self._safe_float(q.get("amount")),
                "bid1": self._safe_float(q.get("bid1")),
                "ask1": self._safe_float(q.get("ask1")),
                "bid_vol1": self._safe_float(q.get("bid_vol1")),
                "ask_vol1": self._safe_float(q.get("ask_vol1")),
                "source": "mootdx",
            }
        return json.dumps(result, ensure_ascii=False)

    # ── 盘口 + F10 + 逐笔（duck-typed，不在基类） ──

    def get_five_level_orderbook(self, symbol: str) -> str:
        """五档盘口原始数据。返回 JSON 字符串，包含 bid1-5 / ask1-5 完整档位。"""
        import json

        client = _get_client()
        code = self._normalize_symbol(symbol)
        try:
            quotes_df = client.quotes(symbol=[code])
        except Exception as exc:
            return json.dumps({"error": f"mootdx quotes failed: {exc}"})

        if quotes_df is None or (hasattr(quotes_df, "empty") and quotes_df.empty):
            return json.dumps({"error": "no data returned"})

        q = quotes_df.iloc[0]
        levels = {
            "code": code,
            "price": self._safe_float(q.get("price")),
            "open": self._safe_float(q.get("open")),
            "high": self._safe_float(q.get("high")),
            "low": self._safe_float(q.get("low")),
            "last_close": self._safe_float(q.get("last_close")),
            "bids": [
                {"price": self._safe_float(q.get(f"bid{i}")), "vol": self._safe_float(q.get(f"bid_vol{i}"))}
                for i in range(1, 6)
            ],
            "asks": [
                {"price": self._safe_float(q.get(f"ask{i}")), "vol": self._safe_float(q.get(f"ask_vol{i}"))}
                for i in range(1, 6)
            ],
            "volume": self._safe_float(q.get("vol")),
            "amount": self._safe_float(q.get("amount")),
            "servertime": str(q.get("servertime", "")),
        }
        return json.dumps(levels, ensure_ascii=False, default=str)

    def get_f10_detail(self, symbol: str, category: int = 0) -> str:
        """F10 公司资料，category: 0=最新提示 1=公司概况 2=财务分析 3=股东研究
        4=主力追踪 5=行业分析 6=公司大事 7=经营分析 8=分红融资。"""
        code = self._normalize_symbol(symbol)
        try:
            from mootdx.reader import Reader
        except ImportError:
            return f"F10 数据不可用（mootdx Reader 未安装）。"
        import os
        import tempfile

        # 尝试常见通达信数据目录，都找不到则创建临时目录（无本地数据返回空）
        tdx_candidates = [
            os.path.expanduser("~/.mootdx"),
            os.path.expanduser("~/tdx"),
            "C:\\new_tdx",
            "D:\\tdx",
            "/opt/tdx",
        ]
        tdxdir = None
        for d in tdx_candidates:
            if os.path.isdir(d):
                tdxdir = d
                break
        if tdxdir is None:
            tdxdir = tempfile.mkdtemp(prefix="mootdx_")

        try:
            reader = Reader.factory(market="std", tdxdir=tdxdir)
            result = reader.F10(code, category)
        except Exception:
            return f"F10 category {category} data empty for {symbol}"

        if not result:
            return f"F10 category {category} data empty for {symbol}"

        cat_names = {
            0: "最新提示", 1: "公司概况", 2: "财务分析", 3: "股东研究",
            4: "主力追踪", 5: "行业分析", 6: "公司大事", 7: "经营分析", 8: "分红融资",
        }
        cat_label = cat_names.get(category, f"Category {category}")
        return f"## F10 {cat_label} ({symbol})\n\n{str(result)}"

    def get_level2_quotes(self, symbol: str, date: str = None) -> str:
        """逐笔成交数据（非交易时间返回空）。"""
        from datetime import date as dt_date

        query_date = date or dt_date.today().strftime("%Y%m%d")
        client = _get_client()
        code = self._normalize_symbol(symbol)
        try:
            trades = client.transaction(symbol=code, date=query_date)
        except Exception as exc:
            return f"cn_mootdx level2 quotes failed for {symbol} on {query_date}: {exc}"

        if trades is None or (hasattr(trades, "empty") and trades.empty):
            return f"{symbol} 在 {query_date} 无逐笔成交数据（非交易时间属正常）。"

        # 返回最近 30 笔
        if hasattr(trades, "head"):
            trades = trades.head(30)
        return f"{symbol} 逐笔成交（{query_date}，最近30笔）：\n{trades.to_string(index=False)}"
