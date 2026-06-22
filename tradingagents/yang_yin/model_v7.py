"""阳谱模型 v0.7 — 岭回归（150天面板, 110天训练, 5折CV）

数据源对齐技术文档: panel_150d + 20251230~20260618(110天) + 5折CV
MAE: 1.93% (文档1.96%)  RMSE: 2.45% (文档2.58%)
"""

import numpy as np

FEATURE_COLS = [
    "trend_mean", "trend_yang", "momentum_mean", "momentum_yang",
    "supply_demand_mean", "supply_demand_yang", "divergence_mean", "divergence_yang",
    "obv_mean", "obv_yang", "vol_extreme_mean",
    "volprice_new_mean", "volprice_new_yang",
    "rsi_mean", "rsi_yang", "strength_mean", "strength_yang",
    "money_mean", "money_yang", "prev_yangpu",
]

INTERCEPT = 46.0000

COEF: dict[str, float] = {
    "trend_mean": 18.8861, "trend_yang": -0.3405,
    "momentum_mean": -0.4761, "momentum_yang": -0.3405,
    "supply_demand_mean": -0.3405, "supply_demand_yang": -0.3405,
    "divergence_mean": -1.3640, "divergence_yang": 1.0584,
    "obv_mean": -1.3359, "obv_yang": 0.1317,
    "vol_extreme_mean": -0.7063,
    "volprice_new_mean": -1.2976, "volprice_new_yang": 0.8027,
    "rsi_mean": -0.1498, "rsi_yang": 0.7735,
    "strength_mean": 1.4547, "strength_yang": 0.2550,
    "money_mean": 0.0000, "money_yang": 0.0000,
    "prev_yangpu": 6.1723,
}

X_MEAN: dict[str, float] = {
    "trend_mean": 0.4699, "trend_yang": 0.4711,
    "momentum_mean": 0.0340, "momentum_yang": 0.4711,
    "supply_demand_mean": -0.0579, "supply_demand_yang": 0.4711,
    "divergence_mean": 0.1744, "divergence_yang": 0.3459,
    "obv_mean": 0.0772, "obv_yang": 0.2618,
    "vol_extreme_mean": 1.0431,
    "volprice_new_mean": 0.0410, "volprice_new_yang": 0.0653,
    "rsi_mean": 49.4457, "rsi_yang": 0.4869,
    "strength_mean": -0.0022, "strength_yang": 0.1244,
    "money_mean": 0.0000, "money_yang": 0.0000,
    "prev_yangpu": 46.0909,
}

X_STD: dict[str, float] = {
    "trend_mean": 0.2153, "trend_yang": 0.2262,
    "momentum_mean": 1.4169, "momentum_yang": 0.2262,
    "supply_demand_mean": 0.4524, "supply_demand_yang": 0.2262,
    "divergence_mean": 0.2403, "divergence_yang": 0.1527,
    "obv_mean": 0.2271, "obv_yang": 0.1276,
    "vol_extreme_mean": 0.1740,
    "volprice_new_mean": 1.5592, "volprice_new_yang": 0.0547,
    "rsi_mean": 8.8809, "rsi_yang": 0.2325,
    "strength_mean": 0.1965, "strength_yang": 0.0869,
    "money_mean": 1.0000, "money_yang": 1.0000,
    "prev_yangpu": 22.7810,
}


def predict_yangpu(factors: dict[str, float]) -> float:
    coef_arr = np.array([COEF[f] for f in FEATURE_COLS], dtype=np.float64)
    mean_arr = np.array([X_MEAN[f] for f in FEATURE_COLS], dtype=np.float64)
    std_arr = np.array([X_STD[f] for f in FEATURE_COLS], dtype=np.float64)

    raw = np.array([factors.get(f, 0.0) or 0.0 for f in FEATURE_COLS], dtype=np.float64)
    if not np.isfinite(raw).all():
        return 50.0
    scaled = (raw - mean_arr) / std_arr
    result = float(scaled @ coef_arr + INTERCEPT)
    if result < 0:
        return 0.0
    if result > 100:
        return 100.0
    return result
