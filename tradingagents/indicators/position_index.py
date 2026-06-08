"""
超买超卖位置指标（Position Index）

基于34日价格区间的百分位位置，用于判断超买超卖状态。
公式来源：通达信风险控制指标
"""

import pandas as pd
import numpy as np


def calculate_position_index(
    df: pd.DataFrame,
    period: int = 14,
    smooth: int = 5,
) -> pd.DataFrame:
    """
    计算超买超卖位置指标（滚动窗口，无漂移不钝化）

    公式来源：通达信滚动位置强弱指标
    基于滚动高低点计算当前位置百分位，
    价格涨跌会自动更新高低点，避免全历史的钝化问题。

    Args:
        df: 包含 open, high, low, close 列的 DataFrame
        period: 滚动周期，默认90
        smooth: EMA平滑周期，默认3

    Returns:
        DataFrame with columns: position_index, zone
    """
    result = df.copy()

    # 滚动高低点
    hhv = result['high'].rolling(window=period).max()
    llv = result['low'].rolling(window=period).min()

    # 计算当前位置百分比 (0-100)
    position = (result['close'] - llv) / (hhv - llv) * 100

    # EMA平滑
    result['position_index'] = position.ewm(span=smooth, adjust=False).mean()

    # 判断区域
    def get_zone(val):
        if pd.isna(val):
            return 'unknown'
        if val >= 80:
            return 'overbought'  # 超买区
        elif val >= 60:
            return 'high'        # 偏高区
        elif val >= 40:
            return 'neutral'     # 中性区
        elif val >= 20:
            return 'low'         # 偏低区
        else:
            return 'oversold'    # 超卖区

    result['zone'] = result['position_index'].apply(get_zone)

    return result


def get_position_signal(df: pd.DataFrame) -> dict:
    """
    获取位置指标信号

    Args:
        df: 包含 position_index 和 zone 列的 DataFrame

    Returns:
        dict: 信号信息
    """
    if len(df) == 0:
        return {"value": None, "zone": "unknown", "signal": "无数据"}

    latest = df.iloc[-1]
    value = latest.get('position_index')
    zone = latest.get('zone', 'unknown')

    if pd.isna(value):
        return {"value": None, "zone": "unknown", "signal": "数据不足"}

    # 生成信号
    if zone == 'overbought':
        signal = "极度超买，风险极高，考虑减仓"
    elif zone == 'high':
        signal = "偏高，警惕回调"
    elif zone == 'neutral':
        signal = "中性，正常持有"
    elif zone == 'low':
        signal = "偏低，关注机会"
    elif zone == 'oversold':
        signal = "极度超卖，可能见底"
    else:
        signal = "未知"

    return {
        "value": round(float(value), 2),
        "zone": zone,
        "signal": signal,
    }
