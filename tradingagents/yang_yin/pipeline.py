"""数据管线 — 首轮全量下载 + 每日增量更新"""

import os
import time
import logging
from pathlib import Path

import pandas as pd
import numpy as np
import tushare as ts

from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_TUSHARE_TOKEN = os.environ.get(
    "TUSHARE_TOKEN",
    "23651a8611b00bf491c7378d81d0bc6265543153530194be989e6ada",
)

# pro_bar(adj='qfq') 内部调两个API(pro_bar+adj_factor)，都计入200次/分限额
# 所以安全速率 = 200 × 0.8 / 2 = 80次/分
DEFAULT_RATE_LIMIT = 80

# 本地存储根目录
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "yang_yin_cache"
DAILY_DIR_NAME = "daily_k"
SUMMARY_DIR_NAME = "summary"


def _get_pro():
    ts.set_token(_TUSHARE_TOKEN)
    return ts.pro_api()


def get_stock_list(pro=None) -> pd.DataFrame:
    """获取沪深A股列表（排除ST、退市、北交所）"""
    if pro is None:
        pro = _get_pro()
    df = pro.stock_basic(
        exchange="", list_status="L",
        fields="ts_code,symbol,name,area,industry,list_date"
    )
    # 排除北交所 (8开头)
    df = df[~df["ts_code"].str.startswith("8")]
    # 排除ST
    df = df[~df["name"].str.contains("ST", na=False)]
    # 排除上市不足60天的（K线不够算指标）
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
    df = df[df["list_date"] <= cutoff]
    return df.reset_index(drop=True)


class YangYinPipeline:
    """阳谱/阴谱数据管线。

    Parameters
    ----------
    cache_dir: 本地缓存根目录
    rate_limit: 每分钟最大请求数，默认160
    """

    def __init__(self, cache_dir=None, rate_limit=DEFAULT_RATE_LIMIT):
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.daily_dir = self.cache_dir / DAILY_DIR_NAME
        self.summary_dir = self.cache_dir / SUMMARY_DIR_NAME
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.summary_dir.mkdir(parents=True, exist_ok=True)
        self.limiter = RateLimiter(rate_limit)
        self._pro = None

    @property
    def pro(self):
        if self._pro is None:
            self._pro = _get_pro()
        return self._pro

    # ── 辅助 ──────────────────────────────────────────────

    @staticmethod
    def _to_ts_code(symbol: str) -> str:
        """000001 → 000001.SZ / 600519.SH"""
        symbol = str(symbol).zfill(6)
        if "." in symbol:
            return symbol.upper()
        if symbol.startswith(("5", "6", "9")):
            return f"{symbol}.SH"
        return f"{symbol}.SZ"

    def _parquet_path(self, ts_code: str) -> Path:
        return self.daily_dir / f"{ts_code.replace('.', '_')}.parquet"

    # ── 首轮全量下载 ──────────────────────────────────────

    def _download_one(self, ts_code: str, start_date: str, end_date: str, max_retries=3) -> bool:
        """下载单只股前复权日线，含指数退避重试。返回 True=成功"""
        for attempt in range(max_retries):
            self.limiter.acquire()
            try:
                df = ts.pro_bar(
                    ts_code=ts_code, adj="qfq", freq="D",
                    start_date=start_date, end_date=end_date,
                )
                if df is not None and not df.empty:
                    df = df.sort_values("trade_date").reset_index(drop=True)
                    path = self._parquet_path(ts_code)
                    df.to_parquet(path, index=False)
                    return True
                return False
            except Exception as e:
                msg = str(e)
                if "频次" in msg or "频率" in msg:
                    wait = 2 ** attempt + 2  # 2s, 4s, 6s
                    logger.debug(f"{ts_code} 限流，{wait}s后重试 (attempt {attempt+1})")
                    time.sleep(wait)
                else:
                    if attempt == max_retries - 1:
                        logger.warning(f"{ts_code} 下载失败: {e}")
                    else:
                        time.sleep(1)
        return False

    def download_full(self, start_date="20240101", end_date=None):
        """逐股拉前复权日线 → parquet，限速80次/分（pro_bar+adj_factor双调用）。

        可多次执行——已存在的 parquet 跳过（断点续传）。
        """
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")

        stocks = get_stock_list(self.pro)
        total = len(stocks)
        logger.info(f"全量下载开始: {total} 只, {start_date}~{end_date}")

        success, skipped, failed = 0, 0, 0
        t0 = time.monotonic()

        for i, row in stocks.iterrows():
            ts_code = row["ts_code"]
            path = self._parquet_path(ts_code)

            if path.exists():
                skipped += 1
                continue

            if self._download_one(ts_code, start_date, end_date):
                success += 1
            else:
                failed += 1

            if (i + 1) % 200 == 0:
                elapsed = time.monotonic() - t0
                logger.info(
                    f"进度 {i+1}/{total} | 成功{success} 跳过{skipped} 失败{failed} | "
                    f"耗时{elapsed:.0f}s"
                )

        elapsed = time.monotonic() - t0
        logger.info(f"全量下载完成: 成功{success} 跳过{skipped} 失败{failed} | 总耗时{elapsed:.0f}s")

    def retry_failed(self, start_date="20240101", end_date=None):
        """重试所有缓存中缺失的股票（限速60次/分，更保守）"""
        if end_date is None:
            end_date = pd.Timestamp.now().strftime("%Y%m%d")

        stocks = get_stock_list(self.pro)
        missing = [row["ts_code"] for _, row in stocks.iterrows()
                   if not self._parquet_path(row["ts_code"]).exists()]

        if not missing:
            logger.info("无缺失股票，无需重试")
            return

        logger.info(f"重试 {len(missing)} 只缺失股票")
        # 重试用更慢的速度
        self.limiter = RateLimiter(60)

        success, failed = 0, 0
        for ts_code in missing:
            if self._download_one(ts_code, start_date, end_date):
                success += 1
            else:
                failed += 1

        logger.info(f"重试完成: 成功{success} 失败{failed}")

    # ── 每日增量更新 ──────────────────────────────────────

    def update_daily(self, trade_date=None):
        """增量更新: 1次 daily() 拿全市场当日未复权数据 → 推前复权 → 追加入库。

        原理: 今日前复权价 = 昨日前复权收盘 × (今日字段 / 今日pre_close)
             pre_close 是除权调整后的昨收，比值自动包含除权修正。
        """
        if trade_date is None:
            trade_date = pd.Timestamp.now().strftime("%Y%m%d")

        # 1. 一次拿全市场当天数据
        daily_df = self.pro.daily(trade_date=trade_date)
        if daily_df is None or daily_df.empty:
            logger.info(f"{trade_date} 无交易数据（可能非交易日）")
            return 0

        updated = 0
        for _, row in daily_df.iterrows():
            ts_code = row["ts_code"]
            path = self._parquet_path(ts_code)

            if not path.exists():
                continue  # 新股，等首轮全量下载补

            hist = pd.read_parquet(path)
            if "close" not in hist.columns or hist.empty:
                continue

            # 如果当日已有数据（来自pro_bar或之前update），跳过
            if str(trade_date) in hist["trade_date"].values:
                continue

            # 取目标日期之前最后一日的收盘价作为推导基准
            hist_before = hist[hist["trade_date"] < trade_date]
            if hist_before.empty:
                continue
            yesterday_qfq_close = hist_before["close"].iloc[-1]

            pre_close = float(row.get("pre_close", 0) or 0)
            if pre_close == 0:
                continue

            open_v = float(row.get("open", 0) or 0)
            high_v = float(row.get("high", 0) or 0)
            low_v = float(row.get("low", 0) or 0)
            close_v = float(row.get("close", 0) or 0)
            base = yesterday_qfq_close

            qfq_open = round(base * open_v / pre_close, 3)
            qfq_high = round(base * high_v / pre_close, 3)
            qfq_low = round(base * low_v / pre_close, 3)
            qfq_close = round(base * close_v / pre_close, 3)

            new_row = pd.DataFrame([{
                "ts_code": ts_code,
                "trade_date": trade_date,
                "open": round(qfq_open, 3),
                "high": round(qfq_high, 3),
                "low": round(qfq_low, 3),
                "close": round(qfq_close, 3),
                "vol": row.get("vol", None),
                "amount": row.get("amount", None),
            }])

            hist = pd.concat([hist, new_row], ignore_index=True)
            hist.to_parquet(path, index=False)
            updated += 1

        logger.info(f"增量更新 {trade_date}: {updated} 只入库")
        return updated

    # ── 面板数据 ──────────────────────────────────────────

    PANEL_FILENAME = "panel_150d_slim.parquet"
    PANEL_COLS = ["ts_code", "trade_date", "close", "high", "low", "vol", "pct_chg"]

    def build_panel(self, lookback_days=150):
        """遍历所有个股parquet → 合并为单一面板parquet。
        首次构建或重建时调用。
        """
        files = list(self.daily_dir.glob("*.parquet"))
        if not files:
            raise RuntimeError(f"无个股缓存: {self.daily_dir}，请先执行 download_full()")

        logger.info(f"开始构建面板: {len(files)} 只股票, {lookback_days}天回溯")

        frames = []
        for f in files:
            df = pd.read_parquet(f)
            if df.empty or "close" not in df.columns or "trade_date" not in df.columns:
                continue
            df = df.sort_values("trade_date").reset_index(drop=True)
            # 只保留最近N天
            df = df.tail(lookback_days).copy()
            # 计算涨跌幅
            df["pct_chg"] = (df["close"] - df["close"].shift(1)) / df["close"].shift(1) * 100
            # 保留所需列
            cols = [c for c in self.PANEL_COLS if c in df.columns]
            frames.append(df[cols])

        if not frames:
            raise RuntimeError("无法构建面板，所有个股数据为空")

        panel = pd.concat(frames, ignore_index=True)
        path = self.cache_dir / self.PANEL_FILENAME
        panel.to_parquet(path, index=False)
        logger.info(f"面板已保存: {path} ({len(panel)} 行, {panel['ts_code'].nunique()} 只)")
        return panel

    def update_panel(self, trade_date=None):
        """增量追加今日数据到面板。"""
        if trade_date is None:
            trade_date = pd.Timestamp.now().strftime("%Y%m%d")

        panel_path = self.cache_dir / self.PANEL_FILENAME
        if not panel_path.exists():
            logger.warning("面板不存在，调用 build_panel() 首次构建")
            return self.build_panel()

        panel = pd.read_parquet(panel_path)

        daily_df = self.pro.daily(trade_date=trade_date)
        if daily_df is None or daily_df.empty:
            logger.info(f"{trade_date} 无交易数据")
            return panel

        # 取面板中已有股票的前一日收盘价
        prev = panel[panel["trade_date"] == panel["trade_date"].max()].copy()
        prev_map = dict(zip(prev["ts_code"], prev["close"]))

        new_rows = []
        for _, row in daily_df.iterrows():
            ts_code = row["ts_code"]
            prev_close = prev_map.get(ts_code)
            if prev_close is None or prev_close == 0:
                continue

            pre_close_raw = float(row.get("pre_close", 0) or 0)
            if pre_close_raw == 0:
                continue

            base = prev_close
            close_v = round(base * float(row.get("close", 0) or 0) / pre_close_raw, 3)
            high_v = round(base * float(row.get("high", 0) or 0) / pre_close_raw, 3)
            low_v = round(base * float(row.get("low", 0) or 0) / pre_close_raw, 3)
            vol_v = float(row.get("vol", 0) or 0)
            pct_chg = round((close_v - prev_close) / prev_close * 100, 2)

            new_rows.append({
                "ts_code": ts_code,
                "trade_date": trade_date,
                "close": close_v,
                "high": high_v,
                "low": low_v,
                "vol": vol_v,
                "pct_chg": pct_chg,
            })

        if new_rows:
            new_df = pd.DataFrame(new_rows)
            # 删除当日旧数据（防止重复调用导致数据叠加）
            panel = panel[panel["trade_date"] != trade_date]
            panel = pd.concat([panel, new_df], ignore_index=True)
            # 维持150天长度
            cutoff = panel["trade_date"].unique()
            cutoff = sorted(cutoff)[-150:]
            panel = panel[panel["trade_date"].isin(cutoff)]
            panel.to_parquet(panel_path, index=False)
            logger.info(f"面板已更新 {trade_date}: +{len(new_rows)} 行")
        else:
            logger.info(f"面板无新增数据 {trade_date}")

        return panel

    def load_panel(self) -> pd.DataFrame | None:
        """加载面板数据"""
        path = self.cache_dir / self.PANEL_FILENAME
        if not path.exists():
            return None
        return pd.read_parquet(path)

    # ── 特征面板（预计算逐股滚动特征，因子计算秒级）────────

    FEATURE_PANEL_FILE = "panel_features.parquet"

    def build_feature_panel(self):
        """基于面板预计算所有逐股滚动特征 → panel_features.parquet。
        之后因子计算只需按日期过滤+截面聚合，无需 groupby rolling。
        """
        panel = self.load_panel()
        if panel is None or panel.empty:
            raise RuntimeError("先执行 build_panel() / update_panel()")

        panel = panel.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
        g = panel.groupby("ts_code")

        logger.info("计算 MA5 / shift / MA20 ...")
        panel["ma5"] = g["close"].transform(
            lambda x: x.rolling(5, min_periods=1).mean()
        )
        panel["close_5d"] = g["close"].shift(5)
        panel["vol_5d"] = g["vol"].shift(5)
        panel["prev_vol"] = g["vol"].shift(1)
        panel["vol_ma20"] = g["vol"].transform(
            lambda x: x.rolling(20, min_periods=1).mean()
        )

        logger.info("计算 RSI14 ...")
        panel["avg_gain14"] = g["pct_chg"].transform(
            lambda x: x.clip(lower=0).rolling(14, min_periods=1).mean()
        )
        panel["avg_loss14"] = g["pct_chg"].transform(
            lambda x: (-x).clip(lower=0).rolling(14, min_periods=1).mean()
        )
        rs = panel["avg_gain14"] / panel["avg_loss14"].replace(0, np.nan)
        panel["rsi14"] = 100 - 100 / (1 + rs)

        cols = [
            "ts_code", "trade_date",
            "close", "vol", "pct_chg",
            "ma5", "close_5d", "vol_5d", "prev_vol", "vol_ma20",
            "rsi14",
        ]
        panel = panel[cols]

        path = self.cache_dir / self.FEATURE_PANEL_FILE
        panel.to_parquet(path, index=False)
        logger.info(f"特征面板已保存: {path} ({len(panel)} 行)")
        return panel

    def update_feature_panel(self, trade_date=None):
        """更新特征面板 — 当前简单重建（向量化秒级完成）"""
        if trade_date:
            self.update_panel(trade_date)
        return self.build_feature_panel()

    def load_feature_panel(self) -> pd.DataFrame | None:
        path = self.cache_dir / self.FEATURE_PANEL_FILE
        if not path.exists():
            return None
        return pd.read_parquet(path)

    # ── 盘中实时快照 ──────────────────────────────────────

    REALTIME_BATCH_SIZE = 700

    @staticmethod
    def fetch_realtime_snapshot(ts_codes: list[str] | None = None,
                                batch_size: int = None,
                                max_retries: int = 2) -> pd.DataFrame:
        """一次拉全市场实时报价 → DataFrame。单批失败自动重试。

        返回:
            DataFrame 列: ts_code, price, vol, amount, open,
                          high, low, pre_close, pct_chg
            网络全断时返回空 DataFrame（调用方自行判断）
        """
        import time as _time
        batch_sz = batch_size or YangYinPipeline.REALTIME_BATCH_SIZE

        if ts_codes is None:
            stocks = get_stock_list()
            ts_codes = stocks["ts_code"].tolist()

        all_rows = []
        total_batches = (len(ts_codes) + batch_sz - 1) // batch_sz
        failed_batches = 0

        for i in range(0, len(ts_codes), batch_sz):
            batch = ts_codes[i : i + batch_sz]
            code_str = ",".join(batch)

            ok = False
            for attempt in range(max_retries + 1):
                try:
                    df = ts.realtime_quote(ts_code=code_str, src="sina")
                    if df is not None and not df.empty:
                        all_rows.append(df)
                        ok = True
                    break
                except Exception as e:
                    if attempt < max_retries:
                        _time.sleep(1 + attempt)
                    else:
                        logger.debug(f"realtime batch {i//batch_sz+1}/{total_batches} 失败: {e}")

            if not ok:
                failed_batches += 1

            if total_batches > 1 and (i // batch_sz) % 5 == 0:
                _time.sleep(0.3)

        if not all_rows:
            logger.warning(f"realtime_quote 全部失败 ({total_batches} 批无数据)")
            return pd.DataFrame()

        if failed_batches:
            logger.warning(f"realtime_quote {failed_batches}/{total_batches} 批失败")

        raw = pd.concat(all_rows, ignore_index=True)
        raw = raw.rename(columns={
            "TS_CODE": "ts_code", "PRICE": "price", "VOLUME": "vol",
            "AMOUNT": "amount", "OPEN": "open", "HIGH": "high",
            "LOW": "low", "PRE_CLOSE": "pre_close",
            "NAME": "name",
        })
        raw["price"] = raw["price"].astype(float)
        raw["vol"] = raw["vol"].astype(float)
        raw["pre_close"] = raw["pre_close"].astype(float)
        raw["pct_chg"] = ((raw["price"] - raw["pre_close"]) / raw["pre_close"] * 100).round(2)

        cols = ["ts_code", "price", "vol", "amount", "open",
                "high", "low", "pre_close", "pct_chg"]
        return raw[[c for c in cols if c in raw.columns]].reset_index(drop=True)

    # ── 读取缓存 ──────────────────────────────────────────

    def load_stock_history(self, ts_code: str) -> pd.DataFrame | None:
        """加载单只股的前复权日线历史"""
        path = self._parquet_path(ts_code)
        if not path.exists():
            return None
        return pd.read_parquet(path)

    def load_all_histories(self) -> dict[str, pd.DataFrame]:
        """加载所有已缓存股票的历史数据（耗内存，慎用）"""
        result = {}
        for path in self.daily_dir.glob("*.parquet"):
            ts_code = path.stem.replace("_", ".")
            result[ts_code] = pd.read_parquet(path)
        return result

    def cached_stock_count(self) -> int:
        return len(list(self.daily_dir.glob("*.parquet")))
