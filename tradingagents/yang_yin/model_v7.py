"""阳谱近似模型 v0.7 — 岭回归参数（来源：技术文档第4节）"""

import numpy as np

# 因子顺序（与系数/标准化参数对齐）
FEATURE_COLS = [
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
    "prev_yangpu",
]

# 截距
INTERCEPT = 45.9636

# 因子系数
COEF: dict[str, float] = {
    "trend_mean": 18.802,
    "trend_yang": -0.387,
    "momentum_mean": -0.380,
    "momentum_yang": -0.387,
    "supply_demand_mean": -0.387,
    "supply_demand_yang": -0.387,
    "divergence_mean": -1.247,
    "divergence_yang": 0.946,
    "obv_mean": -1.184,
    "obv_yang": 0.160,
    "vol_extreme_mean": -0.520,
    "volprice_new_mean": -1.069,
    "volprice_new_yang": 0.744,
    "rsi_mean": -0.687,
    "rsi_yang": 1.134,
    "strength_mean": 1.344,
    "strength_yang": 0.282,
    "money_mean": 0.000,
    "money_yang": 0.000,
    "prev_yangpu": 6.229,
}

# 标准化参数（训练集统计量）
X_MEAN: dict[str, float] = {
    "trend_mean": 0.4671,
    "trend_yang": 0.4714,
    "momentum_mean": 0.0599,
    "momentum_yang": 0.4714,
    "supply_demand_mean": -0.0572,
    "supply_demand_yang": 0.4714,
    "divergence_mean": 0.1762,
    "divergence_yang": 0.3471,
    "obv_mean": 0.0757,
    "obv_yang": 0.2607,
    "vol_extreme_mean": 1.0420,
    "volprice_new_mean": 0.0665,
    "volprice_new_yang": 0.0651,
    "rsi_mean": 49.4447,
    "rsi_yang": 0.4859,
    "strength_mean": -0.0029,
    "strength_yang": 0.1255,
    "money_mean": 0.0000,
    "money_yang": 0.0000,
    "prev_yangpu": 45.9455,
}

X_STD: dict[str, float] = {
    "trend_mean": 0.2137,
    "trend_yang": 0.2240,
    "momentum_mean": 1.4091,
    "momentum_yang": 0.2240,
    "supply_demand_mean": 0.4480,
    "supply_demand_yang": 0.2240,
    "divergence_mean": 0.2382,
    "divergence_yang": 0.1509,
    "obv_mean": 0.2246,
    "obv_yang": 0.1257,
    "vol_extreme_mean": 0.1720,
    "volprice_new_mean": 1.5482,
    "volprice_new_yang": 0.0537,
    "rsi_mean": 8.7343,
    "rsi_yang": 0.2290,
    "strength_mean": 0.1951,
    "strength_yang": 0.0860,
    "money_mean": 1.0000,
    "money_yang": 1.0000,
    "prev_yangpu": 22.8066,
}


def predict_yangpu(factors: dict[str, float]) -> float:
    """输入21个因子原始值，返回阳谱预测值(0-100)。

    参数:
        factors: {factor_name: raw_value}
        必须包含 prev_yangpu，其他缺失项填0

    返回:
        float: 阳谱近似值 (0-100)
    """
    coef_arr = np.array([COEF[f] for f in FEATURE_COLS], dtype=np.float64)
    mean_arr = np.array([X_MEAN[f] for f in FEATURE_COLS], dtype=np.float64)
    std_arr = np.array([X_STD[f] for f in FEATURE_COLS], dtype=np.float64)

    raw = np.array([factors.get(f, 0.0) or 0.0 for f in FEATURE_COLS], dtype=np.float64)
    scaled = (raw - mean_arr) / std_arr
    return float(scaled @ coef_arr + INTERCEPT)
