"""
成交量洗盘指标（Volume Wash Indicator）

基于通达信公式转换，识别4种量能状态：
- 缩量洗盘(X2): 量<=6日最高量/2 + 价格站稳MA10
- 温和放量(X3): 量>昨日量 + 量<5日最低量×5 + 收阳
- 放量突破(X4): 量>=5日最低量×5 + 收阳
- 普通成交(X5): 不属于以上任何
"""

import pandas as pd
import numpy as np


def calculate_volume_wash(
    df: pd.DataFrame,
    ma_period: int = 10,
) -> pd.DataFrame:
    """
    计算成交量洗盘指标

    Args:
        df: 包含 open, high, low, close, volume 的 DataFrame
        ma_period: MA均线周期，默认10

    Returns:
        DataFrame with columns: vol_wash_type (0=普通, 2=缩量洗盘, 3=温和放量, 4=放量突破)
    """
    result = df.copy()
    vol = result['volume'].astype(float)
    close = result['close'].astype(float)
    open_ = result['open'].astype(float)

    ma = close.rolling(ma_period).mean()

    # X_1: 上穿MA到现在的天数
    cross_up = (close > ma) & (close.shift(1) <= ma.shift(1))
    bars_since_cross = pd.Series(np.nan, index=result.index)
    counter = np.nan
    for i in range(len(result)):
        if cross_up.iloc[i]:
            counter = 0
        if not np.isnan(counter):
            bars_since_cross.iloc[i] = counter
            counter += 1

    # X_2: 缩量洗盘
    # 量<=6日最高量/2 AND 上穿以来每天都站在MA上方 AND 昨日最低价>MA
    hhv_vol_6 = vol.rolling(6).max()
    x2_vol_ok = vol <= hhv_vol_6 / 2

    # 检查上穿以来每天都站在MA上方
    x2_above_ma = pd.Series(True, index=result.index)
    for i in range(len(result)):
        if not np.isnan(bars_since_cross.iloc[i]):
            n = int(bars_since_cross.iloc[i])
            if n > 0 and i >= n:
                window = close.iloc[i - n + 1: i + 1]
                ma_window = ma.iloc[i - n + 1: i + 1]
                if (window <= ma_window).any():
                    x2_above_ma.iloc[i] = False

    x2_yesterday_low = result['low'].shift(1) > ma
    x2 = x2_vol_ok & x2_above_ma & x2_yesterday_low

    # X_3: 温和放量上涨
    x3 = (vol > vol.shift(1)) & (vol < vol.rolling(5).min() * 5) & (close > open_)

    # X_4: 放量突破
    x4 = (vol >= vol.rolling(5).min() * 5) & (close > open_)

    # 分类: 0=普通, 2=缩量洗盘, 3=温和放量, 4=放量突破
    wash_type = pd.Series(0, index=result.index, dtype=int)
    wash_type[x2] = 2
    wash_type[x3 & ~x2] = 3
    wash_type[x4 & ~x2 & ~x3] = 4

    result['vol_wash_type'] = wash_type

    return result


def get_volume_wash_signal(df: pd.DataFrame) -> dict:
    """
    获取最新一天的成交量洗盘信号

    Args:
        df: 包含 vol_wash_type 列的 DataFrame

    Returns:
        dict: 信号信息
    """
    if len(df) == 0:
        return {"value": None, "type": "unknown", "signal": "无数据"}

    latest = df.iloc[-1]
    wash_type = int(latest.get('vol_wash_type', 0))

    type_map = {
        0: ("普通", "无特殊量能信号"),
        2: ("缩量洗盘", "筹码稳定，关注低吸机会"),
        3: ("温和放量", "资金试探性介入"),
        4: ("放量突破", "资金强势介入，关注突破确认"),
    }

    type_name, signal = type_map.get(wash_type, ("未知", "未知状态"))

    return {
        "value": wash_type,
        "type": type_name,
        "signal": signal,
    }
