"""
K线形态识别 — 经典日本蜡烛图形态

所有形态基于 OHLC 数据计算，无外部依赖。
输出布尔 Series，可直��作为 backtest 筛选条件。
"""

import numpy as np
import pandas as pd


def _trend_direction(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """简单趋势判定：近 window 日收盘价斜率方向（卷积向量化，O(n)）"""
    closes = df["close"].values
    n = len(closes)
    if n < window:
        return pd.Series(np.zeros(n, dtype=int), index=df.index, dtype=int)
    # OLS slope via convolution: x_centered = [-(w-1)/2, ..., (w-1)/2]
    half = (window - 1) / 2.0
    x_centered = np.arange(window) - half
    denom = (x_centered ** 2).sum()
    kernel = x_centered / denom
    slopes = np.convolve(closes, kernel[::-1], mode="valid")
    avgs = np.convolve(closes, np.ones(window) / window, mode="valid")
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(avgs != 0, slopes / avgs, 0.0)
    dirs = np.where(ratio > 0.002, 1, np.where(ratio < -0.002, -1, 0))
    result = np.concatenate([np.zeros(window - 1, dtype=int), dirs.astype(int)])
    return pd.Series(result[:n], index=df.index, dtype=int)


def _prev_body_low(df: pd.DataFrame) -> pd.Series:
    return np.minimum(df["open"].shift(1), df["close"].shift(1))


def _prev_body_high(df: pd.DataFrame) -> pd.Series:
    return np.maximum(df["open"].shift(1), df["close"].shift(1))


# ============================================================
# 单K线形态
# ============================================================


def is_hammer(df: pd.DataFrame) -> pd.Series:
    """锤子线：下影>2x实体，上影极短，实体小，在下跌趋势中"""
    c = df["close"]
    o = df["open"]
    body = (c - o).abs()
    lower = np.minimum(c, o) - df["low"]
    upper = df["high"] - np.maximum(c, o)
    amp = df["high"] - df["low"]

    trend = _trend_direction(df)
    cond = (
        (lower > 2 * body)  # 下影 > 2x 实体
        & (upper < 0.3 * lower)  # 上影 < 0.3x 下影
        & (body > 0)  # 有实体
        & (body < 0.6 * amp)  # 非十字星
        & (trend == -1)  # 下跌趋势中
    )
    return cond


def is_hanging_man(df: pd.DataFrame) -> pd.Series:
    """吊颈线：同锤子线形态，但在上涨趋势中"""
    c = df["close"]
    o = df["open"]
    body = (c - o).abs()
    lower = np.minimum(c, o) - df["low"]
    upper = df["high"] - np.maximum(c, o)
    amp = df["high"] - df["low"]

    trend = _trend_direction(df)
    cond = (
        (lower > 2 * body)
        & (upper < 0.3 * lower)
        & (body > 0)
        & (body < 0.6 * amp)
        & (trend == 1)
    )
    return cond


def is_shooting_star(df: pd.DataFrame) -> pd.Series:
    """射击之星：上影>2x实体，下影极短，实体小，在上涨趋势中"""
    c = df["close"]
    o = df["open"]
    body = (c - o).abs()
    lower = np.minimum(c, o) - df["low"]
    upper = df["high"] - np.maximum(c, o)
    amp = df["high"] - df["low"]

    trend = _trend_direction(df)
    cond = (
        (upper > 2 * body)
        & (lower < 0.3 * upper)
        & (body > 0)
        & (body < 0.6 * amp)
        & (trend == 1)
    )
    return cond


def is_inverted_hammer(df: pd.DataFrame) -> pd.Series:
    """倒锤子：同射击之星形态，但在下跌趋势中"""
    c = df["close"]
    o = df["open"]
    body = (c - o).abs()
    lower = np.minimum(c, o) - df["low"]
    upper = df["high"] - np.maximum(c, o)
    amp = df["high"] - df["low"]

    trend = _trend_direction(df)
    cond = (
        (upper > 2 * body)
        & (lower < 0.3 * upper)
        & (body > 0)
        & (body < 0.6 * amp)
        & (trend == -1)
    )
    return cond


def is_doji(df: pd.DataFrame, threshold: float = 0.1) -> pd.Series:
    """十字星：实体极小（<振幅的10%）"""
    body = (df["close"] - df["open"]).abs()
    amp = df["high"] - df["low"]
    return (body < threshold * amp) & (amp > 0)


# ============================================================
# 双K线形态
# ============================================================


def is_bullish_engulfing(df: pd.DataFrame) -> pd.Series:
    """看涨吞没：前阴后阳，阳线实体完全包住前阴实体"""
    c = df["close"]
    o = df["open"]
    pc = c.shift(1)
    po = o.shift(1)

    prev_bearish = pc < po
    curr_bullish = c > o
    engulfs = (o <= pc) & (c >= po)  # 当前开盘<=前收(阴) 且 当前收盘>=前开(阴)

    return prev_bearish & curr_bullish & engulfs


def is_bearish_engulfing(df: pd.DataFrame) -> pd.Series:
    """看跌吞没：前阳后阴，阴线实体完全包住前阳实体"""
    c = df["close"]
    o = df["open"]
    pc = c.shift(1)
    po = o.shift(1)

    prev_bullish = pc > po
    curr_bearish = c < o
    engulfs = (o >= pc) & (c <= po)

    return prev_bullish & curr_bearish & engulfs


def is_piercing_pattern(df: pd.DataFrame) -> pd.Series:
    """刺透形态：前阴后阳，阳线收盘超过前阴实体中点，且开盘低于前收"""
    c = df["close"]
    o = df["open"]
    pc = c.shift(1)
    po = o.shift(1)

    prev_bearish = pc < po
    prev_mid = (pc + po) / 2
    cond = (
        prev_bearish
        & (c > o)  # 当前收阳
        & (o < pc)  # 开盘低于前收
        & (c > prev_mid)  # 收盘超过前阴中点
        & (c < po)  # 未完全吞没（区别于吞没形态）
    )
    return cond


def is_dark_cloud_cover(df: pd.DataFrame) -> pd.Series:
    """乌云盖顶：前阳后阴，阴线收盘低于前阳实体中点，且开盘高于前收"""
    c = df["close"]
    o = df["open"]
    pc = c.shift(1)
    po = o.shift(1)

    prev_bullish = pc > po
    prev_mid = (pc + po) / 2
    cond = (
        prev_bullish
        & (c < o)  # 当前收阴
        & (o > pc)  # 开盘高于前收
        & (c < prev_mid)  # 收盘低于前阳中点
        & (c > po)  # 未完全吞没
    )
    return cond


def is_harami(df: pd.DataFrame) -> pd.Series:
    """孕线：今日实体被昨日实体完全包含"""
    c = df["close"]
    o = df["open"]
    pc = c.shift(1)
    po = o.shift(1)

    prev_body_h = np.maximum(pc, po)
    prev_body_l = np.minimum(pc, po)
    curr_body_h = np.maximum(c, o)
    curr_body_l = np.minimum(c, o)

    return (
        (curr_body_h < prev_body_h)
        & (curr_body_l > prev_body_l)
        & ((pc - po).abs() > 0)  # 前日有实体
        & ((c - o).abs() > 0)  # 今日有实体
    )


def is_bullish_harami(df: pd.DataFrame) -> pd.Series:
    """看涨孕线：前阴后阳的孕线，在下跌趋势中"""
    trend = _trend_direction(df)
    return (
        is_harami(df)
        & (df["close"].shift(1) < df["open"].shift(1))  # 前阴
        & (df["close"] > df["open"])  # 今阳
        & (trend == -1)
    )


def is_bearish_harami(df: pd.DataFrame) -> pd.Series:
    """看跌孕线：前阳后阴的孕线，在上涨趋势中"""
    trend = _trend_direction(df)
    return (
        is_harami(df)
        & (df["close"].shift(1) > df["open"].shift(1))  # 前阳
        & (df["close"] < df["open"])  # 今阴
        & (trend == 1)
    )


# ============================================================
# 三K线形态
# ============================================================


def is_morning_star(df: pd.DataFrame) -> pd.Series:
    """启明星：阴线 + 小实体/十字星 + 阳线吞没超过前阴中点"""
    c = df["close"]
    o = df["open"]
    p1c = c.shift(2)  # 前前日
    p1o = o.shift(2)
    p2c = c.shift(1)  # 前日(星)
    p2o = o.shift(1)

    bar1_bearish = p1c < p1o  # 第一根阴线
    bar1_body = (p1c - p1o).abs()
    bar2_body = (p2c - p2o).abs()  # 第二根小实体
    bar3_bullish = c > o  # 第三根阳线

    bar1_mid = (p1c + p1o) / 2

    return (
        bar1_bearish
        & (bar2_body < 0.3 * bar1_body)  # 星体 < 前阴实体的30%
        & bar3_bullish
        & (c > bar1_mid)  # 阳线收盘超过前阴中点
    )


def is_evening_star(df: pd.DataFrame) -> pd.Series:
    """黄昏星：阳线 + 小实体/十字星 + 阴线跌破超过前阳中点"""
    c = df["close"]
    o = df["open"]
    p1c = c.shift(2)
    p1o = o.shift(2)
    p2c = c.shift(1)
    p2o = o.shift(1)

    bar1_bullish = p1c > p1o  # 第一根阳线
    bar1_body = (p1c - p1o).abs()
    bar2_body = (p2c - p2o).abs()
    bar3_bearish = c < o

    bar1_mid = (p1c + p1o) / 2

    return (
        bar1_bullish
        & (bar2_body < 0.3 * bar1_body)
        & bar3_bearish
        & (c < bar1_mid)
    )


def is_three_white_soldiers(df: pd.DataFrame) -> pd.Series:
    """红三兵：连续3根阳线，每根收盘高于前日收盘，实体逐步增大"""
    c = df["close"]
    o = df["open"]
    c1 = c.shift(2)
    o1 = o.shift(2)
    c2 = c.shift(1)
    o2 = o.shift(1)

    b1 = (c1 - o1).abs()
    b2 = (c2 - o2).abs()
    b3 = (c - o).abs()

    return (
        (c1 > o1) & (c2 > o2) & (c > o)  # 三阳
        & (c2 > c1) & (c > c2)  # 收盘递升
        & (b2 > b1 * 0.8) & (b3 > b2 * 0.8)  # 实体不萎缩
    )


def is_three_black_crows(df: pd.DataFrame) -> pd.Series:
    """三只乌鸦：连续3根阴线，每根收盘低于前日收盘，实体逐步增大"""
    c = df["close"]
    o = df["open"]
    c1 = c.shift(2)
    o1 = o.shift(2)
    c2 = c.shift(1)
    o2 = o.shift(1)

    b1 = (c1 - o1).abs()
    b2 = (c2 - o2).abs()
    b3 = (c - o).abs()

    return (
        (c1 < o1) & (c2 < o2) & (c < o)  # 三阴
        & (c2 < c1) & (c < c2)  # 收盘递减
        & (b2 > b1 * 0.8) & (b3 > b2 * 0.8)
    )


# ============================================================
# 批量计算 & 导出
# ============================================================

_PATTERNS = {
    # 单K线
    "hammer": ("锤子线", is_hammer),
    "hanging_man": ("吊颈线", is_hanging_man),
    "shooting_star": ("射击之星", is_shooting_star),
    "inverted_hammer": ("倒锤子", is_inverted_hammer),
    "doji": ("十字星", is_doji),
    # 双K线
    "bullish_engulfing": ("看涨吞没", is_bullish_engulfing),
    "bearish_engulfing": ("看跌吞没", is_bearish_engulfing),
    "piercing": ("刺透形态", is_piercing_pattern),
    "dark_cloud_cover": ("乌云盖顶", is_dark_cloud_cover),
    "bullish_harami": ("看涨孕线", is_bullish_harami),
    "bearish_harami": ("看跌孕线", is_bearish_harami),
    # 三K线
    "morning_star": ("启明星", is_morning_star),
    "evening_star": ("黄昏星", is_evening_star),
    "three_white_soldiers": ("红三兵", is_three_white_soldiers),
    "three_black_crows": ("三只乌鸦", is_three_black_crows),
}


def compute_all_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有K线形态，返回添加了形态列的 DataFrame"""
    result = df.copy()
    for key, (name, func) in _PATTERNS.items():
        result[f"pattern_{key}"] = func(df)
    return result


def get_active_patterns(df: pd.DataFrame) -> dict[str, str]:
    """返回最新一天触发的形态列表 {key: name}"""
    if len(df) == 0:
        return {}
    active = {}
    last_idx = df.index[-1]
    for key, (name, func) in _PATTERNS.items():
        series = func(df)
        if series.loc[last_idx]:
            active[key] = name
    return active


def pattern_registry() -> list[dict]:
    """返回所有形态的元数据，供 factor_pool 注册使用"""
    return [
        {
            "name": name,
            "key": key,
            "column": f"pattern_{key}",
            "category": "K线形态",
            "frequency": "日频",
            "description": f"{name}形态出现时为 True",
        }
        for key, (name, _) in _PATTERNS.items()
    ]


def trend_direction(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """暴露趋势方向供外部使用: 1=涨, -1=跌, 0=震荡"""
    return _trend_direction(df, window)
