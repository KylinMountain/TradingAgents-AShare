"""
布林乖离指标（Bollinger Deviation Indicator）

基于通达信公式转换的布林带乖离指标：
- MA20 = 20日均线
- MCCD = 2 * (C - MA20) * VOL（柱状图，量价乖离强度）
- UP = MA20 + 2 * STD(CLOSE, 21)（布林上轨）
- LP = MA20 - 2 * STD(CLOSE, 20)（布林下轨）
- UB = 1.618 * (UP - MA20)（斐波那契上延展）
- LB = 1.618 * (LP - MA20)（斐波那契下延展）
- UUB = 2.33 * (UP - MA20)（极端上延展）
- LLB = 2.33 * (LP - MA20)（极端下延展）

信号：
- 乖离反转：收盘价上穿 LP 下轨
- 顶部警示：MCCD 突破 UUB 且当日收阴/收跌
"""

import pandas as pd
import numpy as np


def calculate_bollinger_deviation(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算布林乖离指标

    Args:
        df: 包含 open, high, low, close, volume 的 DataFrame

    Returns:
        DataFrame with columns: mccd, ub, lb, uub, llb, open, close, volume,
        is_cross_lp, is_warning
    """
    result = df.copy()
    close = result['close'].astype(float)
    open_ = result['open'].astype(float)
    if 'volume' in result.columns:
        volume = result['volume'].astype(float)
    elif 'amount' in result.columns:
        # amount单位可能为元/千元/万元（取决于数据源），统一折算为手对齐tushare volume
        # amount(元) / close(元/股) = 股 → /100 = 手
        volume = result['amount'].astype(float) / close / 100
    else:
        volume = pd.Series(1.0, index=result.index)  # fallback: use close diff only

    # MA20
    ma20 = close.rolling(20).mean()

    # MCCD = 2 * (C - MA20) * volume
    mccd = 2 * (close - ma20) * volume
    result['mccd'] = mccd

    # UP = MA20 + 2*STD(CLOSE, 21)
    std_up = close.rolling(21).std()
    up = ma20 + 2 * std_up

    # LP = MA20 - 2*STD(CLOSE, 20)
    std_lp = close.rolling(20).std()
    lp = ma20 - 2 * std_lp

    # Band widths scaled by avg volume to match MCCD units (price * volume)
    avg_vol = volume.rolling(20).mean()
    ub = 1.618 * (up - ma20) * avg_vol
    lb = 1.618 * (lp - ma20) * avg_vol
    uub = 2.33 * (up - ma20) * avg_vol
    llb = 2.33 * (lp - ma20) * avg_vol

    result['ub'] = ub
    result['lb'] = lb
    result['uub'] = uub
    result['llb'] = llb

    # CROSS(C, LP): close crosses above LP
    cross_lp = (close > lp) & (close.shift(1) <= lp.shift(1))
    result['is_cross_lp'] = cross_lp

    # MCCD > UUB AND (C < O OR C < REF(C,1))
    is_warning = (mccd > uub) & ((close < open_) | (close < close.shift(1)))
    result['is_warning'] = is_warning

    result['ma20'] = ma20
    result['lp'] = lp

    return result


def get_bollinger_deviation_signal(df: pd.DataFrame) -> dict:
    """
    获取最新一天的布林乖离信号

    Args:
        df: 包含布林乖离指标列的 DataFrame

    Returns:
        dict: {value, type, signal, mccd, ub, lb, uub, llb}
    """
    if len(df) == 0:
        return {"value": 0, "type": "无数据", "signal": "无数据"}

    latest = df.iloc[-1]
    mccd_val = float(latest.get('mccd', 0)) if pd.notna(latest.get('mccd')) else 0
    is_cross_lp = bool(latest.get('is_cross_lp', False))
    is_warning = bool(latest.get('is_warning', False))

    if is_cross_lp and is_warning:
        type_name = "乖离反转+顶部警示"
        signal_text = "双重信号，密切关注方向选择"
    elif is_cross_lp:
        type_name = "乖离反转"
        signal_text = "收盘价上穿下轨，短线反弹信号"
    elif is_warning:
        type_name = "顶部警示"
        signal_text = "MCCD突破极端上轨且收阴，注意回落风险"
    elif pd.notna(latest.get('llb')):
        llb_v = float(latest['llb'])
        lb_v = float(latest['lb'])
        if mccd_val < llb_v:
            type_name = "极端超卖"
            signal_text = "MCCD跌破极端下轨，超跌区域关注反弹"
        elif mccd_val < lb_v:
            type_name = "超卖"
            signal_text = "MCCD跌破斐波那契下轨，偏弱但接近支撑"
        else:
            ub_v = float(latest['ub'])
            if mccd_val > ub_v:
                type_name = "超买"
                signal_text = "MCCD突破斐波那契上轨，偏强但注意回调"
            else:
                type_name = "中性"
                signal_text = "MCCD在正常区间运行"
    else:
        type_name = "中性"
        signal_text = "MCCD在正常区间运行"

    return {
        "value": mccd_val,
        "type": type_name,
        "signal": signal_text,
        "mccd": mccd_val,
    }
