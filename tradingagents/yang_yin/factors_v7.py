"""阳谱因子计算 — 20个截面因子 + prev_yangpu惯性因子

基于技术文档 v0.7 第3节因子定义，输入 panel 数据，输出因子 dict → model_v7 预测。

因子分组:
  trend      — 价格>MA5占比, 阳线占比
  momentum   — 涨跌幅均值
  supply_demand — 涨跌方向均值
  divergence — 5日量价背离
  obv        — 当日量价方向
  vol_extreme — 量比均值
  volprice   — 量价交互
  rsi        — 14日RSI
  strength   — 涨跌幅度>3%判定
  money      — 大单净流入(系数=0,跳过)
  prev_yangpu — 外部传入
"""

import numpy as np
import pandas as pd

import logging

logger = logging.getLogger(__name__)

# 因子名列表（对齐 model_v7.FEATURE_COLS，不含 prev_yangpu）
FACTOR_NAMES = [
    "trend_mean",
    "trend_yang",
    "momentum_mean",
    "momentum_yang",
    "supply_demand_mean",
    "supply_demand_yang",
    "divergence_mean",
    "divergence_yang",
    "obv_mean",
    "obv_yang",
    "vol_extreme_mean",
    "volprice_new_mean",
    "volprice_new_yang",
    "rsi_mean",
    "rsi_yang",
    "strength_mean",
    "strength_yang",
    "money_mean",
    "money_yang",
]


def compute_factors(
    panel: pd.DataFrame,
    trade_date: str,
    prev_yangpu: float | None = None,
) -> dict[str, float] | None:
    """计算单个交易日的20个截面因子。

    参数:
        panel: 面板数据 (ts_code, trade_date, close, high, low, vol, pct_chg)
        trade_date: 目标交易日 YYYYMMDD
        prev_yangpu: 前一日阳谱值，None则用50中性值

    返回:
        {factor_name: raw_value} 或 None(无数据)
    """
    all_dates = sorted(panel["trade_date"].unique())
    if trade_date not in all_dates:
        return None

    idx = all_dates.index(trade_date)
    # 回溯20天用于 vol_ma20 和 5日变化
    lookback_start = max(0, idx - 20)
    window_dates = all_dates[lookback_start : idx + 1]

    df = panel[panel["trade_date"].isin(window_dates)].copy()
    # 只保留目标日有数据的股票
    target_stocks = df[df["trade_date"] == trade_date]["ts_code"].unique()
    df = df[df["ts_code"].isin(target_stocks)]

    if df.empty:
        return None

    df = df.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)

    # ── 逐股滚动特征 ──
    g = df.groupby("ts_code")

    df["ma5"] = g["close"].transform(lambda x: x.rolling(5, min_periods=1).mean())
    df["close_5d"] = g["close"].shift(5)
    df["vol_5d"] = g["vol"].shift(5)
    df["prev_vol"] = g["vol"].shift(1)
    df["vol_ma20"] = g["vol"].transform(lambda x: x.rolling(20, min_periods=1).mean())

    # RSI(14) 简单均值版（文档3.2.8）
    gains = df["pct_chg"].clip(lower=0)
    losses = (-df["pct_chg"]).clip(lower=0)
    df["avg_gain14"] = g["pct_chg"].transform(
        lambda x: x.clip(lower=0).rolling(14, min_periods=1).mean()
    )
    df["avg_loss14"] = g["pct_chg"].transform(
        lambda x: (-x).clip(lower=0).rolling(14, min_periods=1).mean()
    )
    rs = df["avg_gain14"] / df["avg_loss14"].replace(0, np.nan)
    df["rsi14"] = 100 - 100 / (1 + rs)

    # ── 过滤到目标日 ──
    day = df[df["trade_date"] == trade_date].copy()
    n = len(day)
    if n == 0:
        return None

    # ── 逐股信号 ──
    above_ma5 = (day["close"] > day["ma5"]).astype(int)
    price_up = (day["pct_chg"] > 0).astype(int)
    sd = np.where(day["pct_chg"] > 0, 1, -1)

    # 背离
    close_5d_ret = (day["close"] - day["close_5d"]) / day["close_5d"].replace(0, np.nan)
    vol_5d_ret = (day["vol"] - day["vol_5d"]) / day["vol_5d"].replace(0, np.nan)
    divergence = pd.Series(0, index=day.index, dtype=float)
    divergence.loc[(close_5d_ret > 0) & (vol_5d_ret < 0)] = -1
    divergence.loc[(close_5d_ret < 0) & (vol_5d_ret < 0)] = 1

    # OBV方向
    obv_dir = pd.Series(0, index=day.index, dtype=float)
    obv_dir.loc[(day["pct_chg"] > 0) & (day["vol"] > day["prev_vol"])] = 1
    obv_dir.loc[(day["pct_chg"] < 0) & (day["vol"] > day["prev_vol"])] = -1

    # 量比
    vol_ratio = day["vol"] / day["vol_ma20"].replace(0, np.nan)

    # 强度
    strength = pd.Series(0, index=day.index, dtype=float)
    strength.loc[day["pct_chg"] > 3] = 1
    strength.loc[day["pct_chg"] < -3] = -1

    # ── 截面聚合 ──
    yang_pct = price_up.mean()
    vol_extreme_mean_val = vol_ratio.mean()
    momentum_mean_val = day["pct_chg"].mean()

    factors = {
        "trend_mean": float(above_ma5.mean()),
        "trend_yang": float(yang_pct),
        "momentum_mean": float(momentum_mean_val),
        "momentum_yang": float(yang_pct),
        "supply_demand_mean": float(sd.mean()),
        "supply_demand_yang": float(yang_pct),
        "divergence_mean": float(divergence.mean()),
        "divergence_yang": float((divergence > 0).mean()),
        "obv_mean": float(obv_dir.mean()),
        "obv_yang": float((obv_dir > 0).mean()),
        "vol_extreme_mean": float(vol_extreme_mean_val),
        "volprice_new_mean": float(momentum_mean_val * vol_extreme_mean_val),
        "volprice_new_yang": float(yang_pct * (vol_ratio > 1.5).mean()),
        "rsi_mean": float(day["rsi14"].mean()),
        "rsi_yang": float((day["rsi14"] > 50).mean()),
        "strength_mean": float(strength.mean()),
        "strength_yang": float((strength > 0).mean()),
        "money_mean": 0.0,
        "money_yang": 0.0,
    }

    factors["prev_yangpu"] = float(prev_yangpu) if prev_yangpu is not None else 50.0

    return factors


def compute_factors_batch(
    panel: pd.DataFrame,
    prev_yangpu_map: dict[str, float] | None = None,
) -> pd.DataFrame:
    """批量计算所有交易日因子，返回 DataFrame (一行一天)。

    参数:
        panel: 面板数据
        prev_yangpu_map: {trade_date: prev_yangpu} 映射，缺失日用50中性值

    返回:
        DataFrame, index=trade_date, columns=因子名 + "yangpu_pred"(预测值)
    """
    from .model_v7 import predict_yangpu

    all_dates = sorted(panel["trade_date"].unique())
    if prev_yangpu_map is None:
        prev_yangpu_map = {}

    rows = []
    for dt in all_dates:
        prev = prev_yangpu_map.get(dt, 50.0)
        factors = compute_factors(panel, dt, prev_yangpu=prev)
        if factors is None:
            continue
        factors["yangpu_pred"] = predict_yangpu(factors)
        rows.append({"trade_date": dt, **factors})

    return pd.DataFrame(rows).set_index("trade_date")
