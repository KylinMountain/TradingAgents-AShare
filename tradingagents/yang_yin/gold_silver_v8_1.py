"""金/银手指 v8.1 — 逻辑回归预测大盘信号（金=1/银=0）

11特征：7个阳谱EMA序列 + 4个全市场面板统计。
"""

import logging

import numpy as np
import pandas as pd

from .pipeline import YangYinPipeline

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "prev_signal",
    "macd_5_10",
    "ema5_slope",
    "delta_1d",
    "bias_vs_ema5",
    "ema5_up_days",
    "ema5_down_days",
    "up_mean",
    "vol_ratio_ma5",
    "limit_up_ma5",
    "mean_chg_ma5",
]

INTERCEPT = 1.7483

COEF = {
    "prev_signal": 1.139, "macd_5_10": 0.597, "ema5_slope": 1.040,
    "delta_1d": 0.825, "bias_vs_ema5": 0.180, "ema5_up_days": 0.443,
    "ema5_down_days": 0.395, "up_mean": 0.678, "vol_ratio_ma5": 1.792,
    "limit_up_ma5": -0.190, "mean_chg_ma5": 1.640,
}

SCALER_MEAN = {
    "prev_signal": 0.1667, "macd_5_10": -0.4153, "ema5_slope": -0.0495,
    "delta_1d": -0.1759, "bias_vs_ema5": -2.8094, "ema5_up_days": 1.3333,
    "ema5_down_days": 1.5833, "up_mean": 2.5818, "vol_ratio_ma5": 1.6049,
    "limit_up_ma5": 103.4019, "mean_chg_ma5": 0.0541,
}

SCALER_STD = {
    "prev_signal": 0.9860, "macd_5_10": 5.7335, "ema5_slope": 6.4091,
    "delta_1d": 14.4080, "bias_vs_ema5": 31.7240, "ema5_up_days": 1.7743,
    "ema5_down_days": 2.0867, "up_mean": 0.5450, "vol_ratio_ma5": 0.6607,
    "limit_up_ma5": 27.3926, "mean_chg_ma5": 0.6042,
}


def _compute_market_from_realtime(realtime_df: pd.DataFrame) -> dict | None:
    """从实时报价DataFrame计算当日市场特征。"""
    if realtime_df.empty:
        return None
    day = realtime_df
    up = day[day["pct_chg"] > 0]
    down = day[day["pct_chg"] < 0]
    up_mean = float(up["pct_chg"].mean()) if not up.empty else 0.0
    up_vol = up["vol"].sum() if not up.empty else 0.0
    down_vol = down["vol"].sum() if not down.empty else 1.0
    vol_ratio_raw = up_vol / max(down_vol, 1.0)
    limit_up_count = int((day["pct_chg"] >= 9.9).sum())
    mean_chg_raw = float(day["pct_chg"].mean())
    return {
        "trade_date": pd.Timestamp.now().strftime("%Y%m%d"),
        "up_mean": up_mean,
        "vol_ratio_raw": vol_ratio_raw,
        "limit_up_count": limit_up_count,
        "mean_chg_raw": mean_chg_raw,
    }


def compute_market_features(panel: pd.DataFrame, trade_date: str) -> dict | None:
    """从面板计算单个日期的4个大盘情绪特征原始值。"""
    day = panel[panel["trade_date"] == trade_date]
    if day.empty:
        return None

    up = day[day["pct_chg"] > 0]
    down = day[day["pct_chg"] < 0]

    up_mean = float(up["pct_chg"].mean()) if not up.empty else 0.0
    up_vol = up["vol"].sum() if not up.empty else 0.0
    down_vol = down["vol"].sum() if not down.empty else 1.0
    vol_ratio_raw = up_vol / max(down_vol, 1.0)
    limit_up_count = int((day["pct_chg"] >= 9.9).sum())
    mean_chg_raw = float(day["pct_chg"].mean())

    return {
        "trade_date": trade_date,
        "up_mean": up_mean,
        "vol_ratio_raw": vol_ratio_raw,
        "limit_up_count": limit_up_count,
        "mean_chg_raw": mean_chg_raw,
    }


def compute_market_features_all(panel: pd.DataFrame) -> pd.DataFrame:
    """计算面板中所有日期的大盘情绪特征，返回DataFrame。"""
    rows = []
    for td in sorted(panel["trade_date"].unique()):
        r = compute_market_features(panel, str(td))
        if r:
            rows.append(r)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["trade_date"] = df["trade_date"].astype(str)
    return df.set_index("trade_date")


def compute_features(
    yang_hist: pd.DataFrame,
    mkt_feat: pd.DataFrame,
    trade_date: str,
    prev_signal: int,
) -> dict | None:
    """计算单个日期的11个特征。"""
    yang_hist = yang_hist.sort_values("trade_date").reset_index(drop=True)
    dates = yang_hist["trade_date"].tolist()
    if trade_date not in dates:
        return None
    idx = dates.index(trade_date)

    yangpu = yang_hist["yang_pct"].values.astype(float)
    ema5 = pd.Series(yangpu).ewm(span=5, adjust=False).mean()
    ema10 = pd.Series(yangpu).ewm(span=10, adjust=False).mean()

    # 7 baseline features
    f_macd = float(ema5.iloc[idx] - ema10.iloc[idx])
    f_slope = float(ema5.iloc[idx] - ema5.iloc[idx - 1]) if idx > 0 else 0.0
    f_delta = float(yangpu[idx] - yangpu[idx - 1]) if idx > 0 else 0.0
    _e5 = float(ema5.iloc[idx])
    f_bias = (float(yangpu[idx]) - _e5) / _e5 * 100.0 if _e5 != 0 else 0.0

    f_up_days = 0
    for j in range(idx - 1, -1, -1):
        sl = float(ema5.iloc[j + 1] - ema5.iloc[j]) if j + 1 < len(ema5) else 0.0
        if sl > 0:
            f_up_days += 1
        else:
            break

    f_down_days = 0
    for j in range(idx - 1, -1, -1):
        sl = float(ema5.iloc[j + 1] - ema5.iloc[j]) if j + 1 < len(ema5) else 0.0
        if sl < 0:
            f_down_days += 1
        else:
            break

    # 4 market features with MA5 smoothing
    f_up_mean = 0.0
    f_vol_ratio_ma5 = 0.0
    f_limit_up_ma5 = 0.0
    f_mean_chg_ma5 = 0.0

    if trade_date in mkt_feat.index:
        # get up to 5 most recent dates including current
        mkt_sorted = mkt_feat.sort_index()
        pos = mkt_sorted.index.get_loc(trade_date)
        if isinstance(pos, slice) or isinstance(pos, np.ndarray):
            pos = pos[0] if len(pos) > 0 else None
        if pos is not None:
            start = max(0, int(pos) - 4)
            window = mkt_sorted.iloc[start : int(pos) + 1]
            f_up_mean = float(mkt_sorted.iloc[int(pos)]["up_mean"])
            f_vol_ratio_ma5 = float(window["vol_ratio_raw"].mean())
            f_limit_up_ma5 = float(window["limit_up_count"].mean())
            f_mean_chg_ma5 = float(window["mean_chg_raw"].mean())

    features = {
        "prev_signal": float(prev_signal),
        "macd_5_10": f_macd,
        "ema5_slope": f_slope,
        "delta_1d": f_delta,
        "bias_vs_ema5": f_bias,
        "ema5_up_days": float(f_up_days),
        "ema5_down_days": float(f_down_days),
        "up_mean": f_up_mean,
        "vol_ratio_ma5": f_vol_ratio_ma5,
        "limit_up_ma5": f_limit_up_ma5,
        "mean_chg_ma5": f_mean_chg_ma5,
    }
    return features


def predict_gold_finger(features: dict) -> tuple[int, float]:
    """返回 (signal, probability): signal=1金, 0银。"""
    z = 0.0
    for f in FEATURE_COLS:
        raw = features.get(f, 0.0) or 0.0
        if not np.isfinite(raw):
            return 1, 0.5
        z += (raw - SCALER_MEAN[f]) / SCALER_STD[f] * COEF[f]
    logit = INTERCEPT + z
    if not np.isfinite(logit):
        return 1, 0.5
    prob = 1.0 / (1.0 + np.exp(-logit))
    signal = 1 if prob >= 0.5 else 0
    return signal, float(prob)


def generate_history(
    panel: pd.DataFrame,
    yang_hist: pd.DataFrame,
    realtime_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """链式回填：按时间顺序计算每日金/银信号。
    盘中传入 realtime_df 补充今日市场特征（panel 尚未更新时）。"""
    if yang_hist.empty:
        return pd.DataFrame()

    yang_hist = yang_hist.sort_values("trade_date").reset_index(drop=True)
    mkt_feat = compute_market_features_all(panel)

    # 盘中：从 realtime 计算今日市场特征，注入 mkt_feat
    if realtime_df is not None and not realtime_df.empty:
        today_feat = _compute_market_from_realtime(realtime_df)
        if today_feat is not None:
            mkt_feat.loc[today_feat["trade_date"]] = [
                today_feat["up_mean"], today_feat["vol_ratio_raw"],
                today_feat["limit_up_count"], today_feat["mean_chg_raw"],
            ]
            logger.info(f"盘中市场特征注入: {today_feat['trade_date']} up_mean={today_feat['up_mean']:.2f} limit_up={today_feat['limit_up_count']}")

    if mkt_feat.empty:
        logger.info("大盘情绪特征为空（盘中面板未更新？），市场特征全部置零")

    # 使用 yang_hist 中的所有日期，不限定 mkt_feat 范围
    dates = yang_hist["trade_date"].tolist()
    if not dates:
        return pd.DataFrame()

    results = []
    prev_signal = 1  # 默认金起步

    for td in dates:
        feats = compute_features(yang_hist, mkt_feat, td, prev_signal)
        if feats is None:
            continue
        signal, prob = predict_gold_finger(feats)
        results.append({"trade_date": td, "signal": signal, "prob": round(prob, 4)})
        prev_signal = signal

    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    logger.info(
        "金/银手指历史生成: %d 天 | 金=%d 银=%d",
        len(df),
        (df["signal"] == 1).sum(),
        (df["signal"] == 0).sum(),
    )
    return df


def _history_path(pipeline: YangYinPipeline = None):
    if pipeline is None:
        pipeline = YangYinPipeline()
    return pipeline.summary_dir / "gold_finger_history.parquet"


def load_gold_finger_history(pipeline: YangYinPipeline = None) -> pd.DataFrame:
    path = _history_path(pipeline)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def save_gold_finger_history(df: pd.DataFrame, pipeline: YangYinPipeline = None):
    if df.empty:
        return
    path = _history_path(pipeline)
    df.to_parquet(path, index=False)
    logger.info(f"金/银手指历史已保存: {path} ({len(df)} 条)")
