"""阳阴判定评分 — 四维技术体检 → 0-4分连续 → 阴阳分类

维度（每个维度0-1分，子条件累加）:
  D1 趋势方向: close>MA5 +0.25, close>MA13 +0.25, close>MA60 +0.25, MA13>MA60 +0.25
  D2 动量强弱: RSI>50 +0.5, MACD柱>0且上升 +0.5(MACD>0不上升+0.25)
  D3 量价配合: 放量上涨1.0, 缩量上涨0.5, 缩量下跌0.5, 放量下跌0.0
  D4 资金状态: 主力净流入>0 → 1.0

输出: total 0-4连续, ≥2.0=阳, <2.0=阴
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 需要的最少历史天数
MIN_HISTORY_DAYS = 120


@dataclass
class StockScore:
    ts_code: str
    symbol: str = ""
    name: str = ""
    trade_date: str = ""
    close: float = 0.0
    # 四个维度子分 (0-1, float)
    d1_trend: float = 0.0
    d2_momentum: float = 0.0
    d3_volume_price: float = 0.0
    d4_capital: float = 0.0
    total: float = 0.0        # 总分 0-4 连续
    label: str = "neutral"    # yang / yin
    # 诊断细节
    details: dict = field(default_factory=dict)


def compute_ma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=window).mean()


def compute_ema(close: pd.Series, window: int) -> pd.Series:
    return close.ewm(span=window, adjust=False, min_periods=window).mean()


def compute_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = compute_ema(dif, signal)
    hist = (dif - dea) * 2  # 柱状图 ×2 对齐行情软件
    return dif, dea, hist


def compute_rsi(close: pd.Series, window=14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ── 单只股评分 ──────────────────────────────────────────

def score_stock(df: pd.DataFrame, fund_flow: float | None = None) -> StockScore | None:
    """对一只股做四维技术体检，返回 StockScore（不足120天K线返回None）。

    Parameters
    ----------
    df: 前复权日线，按 trade_date 升序
    fund_flow: 当日主力净流入（万元），无数据则D4弃权
    """
    if df is None or len(df) < MIN_HISTORY_DAYS:
        return None

    df = df.copy()
    close = df["close"].astype(float)
    vol = df.get("vol", pd.Series([0] * len(df), index=df.index)).astype(float)

    latest_close = close.iloc[-1]
    ts_code = str(df["ts_code"].iloc[-1]) if "ts_code" in df.columns else ""
    trade_date = str(df["trade_date"].iloc[-1]) if "trade_date" in df.columns else ""

    # 计算指标
    ma5 = compute_ma(close, 5)
    ma13 = compute_ma(close, 13)
    ma60 = compute_ma(close, 60)
    dif, dea, macd_hist = compute_macd(close)
    rsi = compute_rsi(close, 14)
    vol_ma20 = compute_ma(vol, 20)

    # 最新值
    ma5_v = ma5.iloc[-1]
    ma13_v = ma13.iloc[-1]
    ma60_v = ma60.iloc[-1]
    macd_hist_v = macd_hist.iloc[-1]
    macd_hist_prev = macd_hist.iloc[-2] if len(macd_hist) >= 2 else macd_hist_v
    rsi_v = rsi.iloc[-1]
    vol_v = vol.iloc[-1]
    vol_ma20_v = vol_ma20.iloc[-1]
    close_prev = close.iloc[-2] if len(close) >= 2 else latest_close

    details = {}

    # ── D1 趋势方向: 4个子条件各0.25 ──
    d1 = 0.0
    details["ma5"] = round(float(ma5_v), 2)
    details["ma13"] = round(float(ma13_v), 2)
    details["ma60"] = round(float(ma60_v), 2)
    details["above_ma5"] = latest_close > ma5_v
    details["above_ma13"] = latest_close > ma13_v
    details["above_ma60"] = latest_close > ma60_v
    details["ma13_above_ma60"] = ma13_v > ma60_v

    if latest_close > ma5_v:
        d1 += 0.25
    if latest_close > ma13_v:
        d1 += 0.25
    if latest_close > ma60_v:
        d1 += 0.25
    if ma13_v > ma60_v:
        d1 += 0.25

    # ── D2 动量强弱: RSI(0.5) + MACD(0.5) ──
    d2 = 0.0
    details["macd_hist"] = round(float(macd_hist_v), 4)
    details["macd_hist_rising"] = macd_hist_v > macd_hist_prev
    details["rsi"] = round(float(rsi_v), 1)

    if rsi_v > 50:
        d2 += 0.5
    if macd_hist_v > 0:
        if macd_hist_v > macd_hist_prev:
            d2 += 0.5  # MACD>0 且继续上升
        else:
            d2 += 0.25  # MACD>0 但不上升

    # ── D3 量价配合: 4档 ──
    d3 = 0.0
    details["vol_ratio"] = round(float(vol_v / vol_ma20_v), 2) if vol_ma20_v > 0 else 0
    details["price_up"] = latest_close > close_prev
    details["vol_gt_ma20"] = vol_v > vol_ma20_v

    price_up = latest_close > close_prev
    vol_active = vol_v > vol_ma20_v

    if price_up:
        if vol_active:
            d3 = 1.0   # 放量上涨 — 最健康
        else:
            d3 = 0.5   # 缩量上涨 — 动能不足
    else:
        if vol_active:
            d3 = 0.0   # 放量下跌 — 最不健康
        else:
            d3 = 0.5   # 缩量下跌 — 抛压不重，相对健康

    # ── D4 资金状态 ──
    d4_val = -1.0  # 标记弃权
    if fund_flow is not None:
        details["fund_flow"] = round(float(fund_flow), 2)
        d4_val = 1.0 if fund_flow > 0 else 0.0
    else:
        details["fund_flow"] = None

    # ── 总分与分类 ──
    if d4_val < 0:
        # 无资金数据，3个有效维度，按比例映射到4分制
        raw_total = d1 + d2 + d3
        total = raw_total * (4.0 / 3.0)
        d4 = 0.0
    else:
        raw_total = d1 + d2 + d3 + d4_val
        total = raw_total
        d4 = d4_val

    if total >= 2.0:
        label = "yang"
    else:
        label = "yin"

    return StockScore(
        ts_code=ts_code,
        trade_date=trade_date,
        close=round(float(latest_close), 2),
        d1_trend=round(d1, 2),
        d2_momentum=round(d2, 2),
        d3_volume_price=round(d3, 2),
        d4_capital=round(d4, 2),
        total=round(total, 2),
        label=label,
        details=details,
    )


# ── 资金流数据辅助 ──────────────────────────────────────

def fetch_batch_fund_flow(ts_codes: list[str], trade_date: str = None,
                          pipeline=None) -> dict[str, float]:
    """获取当日主力净流入（万元）。一次 API 拿全市场。

    Returns {ts_code: net_mf_vol}
    """
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y%m%d")

    import os
    import tushare as ts
    token = os.environ.get("TUSHARE_TOKEN", "23651a8611b00bf491c7378d81d0bc6265543153530194be989e6ada")
    ts.set_token(token)
    pro = ts.pro_api()

    try:
        df = pro.moneyflow(trade_date=trade_date)
        if df is None or df.empty:
            return {}
    except Exception:
        return {}

    # 缓存
    if pipeline is not None:
        cache_dir = pipeline.summary_dir / "moneyflow"
        cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_dir / f"{trade_date}.parquet", index=False)

    result = {}
    for _, row in df.iterrows():
        result[row["ts_code"]] = float(row.get("net_mf_vol", 0) or 0)
    return result
