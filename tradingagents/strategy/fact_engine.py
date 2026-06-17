"""
39条规则 事实计算引擎

纯计算模块：输入股票日K DataFrame，输出带事实列的 DataFrame。
不包含 LLM 调用，无副作用。

事实层 = 7条定义规则 + 辅助列，为 LLM 方法层推理提供"已知事实"。
"""

import numpy as np
import pandas as pd


def compute_facts(df: pd.DataFrame, market_state: str | None = None) -> pd.DataFrame:
    """
    计算所有事实列

    Parameters
    ----------
    df : pd.DataFrame
        需含 open, high, low, close, volume 列，DatetimeIndex 或任意索引
    market_state : str | None
        市场状态 "牛市" / "熊市"，如不传则默认 "未知"

    Returns
    -------
    pd.DataFrame
        原 DataFrame + 所有事实列
    """
    result = df.copy()
    o, h, l, c, v = result["open"], result["high"], result["low"], result["close"], result["volume"]

    # ============================================================
    # 基础量价事实
    # ============================================================

    # 振幅（避免除零）
    amplitude = h - l
    amplitude = amplitude.where(amplitude > 0, 0.001)

    # 实体
    body = (c - o).abs()

    # 影线长度
    body_low_arr = np.minimum(o, c)
    body_high_arr = np.maximum(o, c)
    lower_shadow = body_low_arr - l
    upper_shadow = h - body_high_arr

    # 影线/振幅 比值（跨股可比）
    result["lower_shadow_ratio"] = lower_shadow / amplitude
    result["upper_shadow_ratio"] = upper_shadow / amplitude
    result["body_ratio"] = body / amplitude

    # 实体方向 +1收阳 -1收阴（平盘按0）
    result["body_direction"] = np.sign(c - o).astype(int)

    # 振幅百分比
    result["amplitude_pct"] = amplitude / c

    # ============================================================
    # 规则1：高量定义 — 当日量 > 前3日每一天的量
    # ============================================================
    def _is_high_volume(vol_series: pd.Series) -> pd.Series:
        vol = vol_series.values
        n = len(vol)
        result_arr = np.zeros(n, dtype=bool)
        for i in range(3, n):
            today = vol[i]
            result_arr[i] = today > vol[i - 1] and today > vol[i - 2] and today > vol[i - 3]
        return pd.Series(result_arr, index=vol_series.index)

    result["is_high_volume"] = _is_high_volume(v)

    # ============================================================
    # 量能状态：放量 / 缩量 / 平量 / 地量（5日滚动均量）
    # ============================================================
    ma5_vol = v.rolling(5, min_periods=3).mean()
    vol_ratio = v / ma5_vol
    result["volume_state"] = "平量"
    result.loc[vol_ratio > 1.5, "volume_state"] = "放量"
    result.loc[vol_ratio < 0.75, "volume_state"] = "缩量"
    result.loc[vol_ratio < 0.5, "volume_state"] = "地量"

    # ============================================================
    # 规则9：假阴假阳 — K线颜色与实际涨跌方向背离
    # ============================================================
    prev_c = c.shift(1)
    is_fake = np.zeros(len(result), dtype=bool)
    for i in range(1, len(result)):
        if pd.isna(prev_c.iloc[i]):
            continue
        yang_color = c.iloc[i] > o.iloc[i]   # 红色
        yin_color = c.iloc[i] < o.iloc[i]    # 绿色
        price_up = c.iloc[i] > prev_c.iloc[i]   # 实际涨
        price_down = c.iloc[i] < prev_c.iloc[i]  # 实际跌
        if (yin_color and price_up) or (yang_color and price_down):
            is_fake[i] = True
    result["is_fake"] = is_fake

    # ============================================================
    # 规则4：高量支撑位 — 最近高量柱实体最低点
    # ============================================================
    support_levels = np.full(len(result), np.nan)
    last_support = np.nan
    for i in range(len(result)):
        if result["is_high_volume"].iloc[i]:
            last_support = body_low_arr.iloc[i]
        support_levels[i] = last_support
    result["support_level"] = support_levels

    # ============================================================
    # 规则5：高量压力位 — 过往高量柱实体高低点区间
    # 取价格上方、最近的高量柱实体区间
    # ============================================================
    resistance_high_arr = np.full(len(result), np.nan)
    resistance_low_arr = np.full(len(result), np.nan)
    for i in range(len(result)):
        current_close = c.iloc[i]
        best_idx = -1
        best_high = float("inf")
        for j in range(i):  # 只看过往K线
            if result["is_high_volume"].iloc[j]:
                bh = body_high_arr.iloc[j]
                if bh > current_close and bh < best_high:
                    best_high = bh
                    best_idx = j
        if best_idx >= 0:
            resistance_high_arr[i] = body_high_arr.iloc[best_idx]
            resistance_low_arr[i] = body_low_arr.iloc[best_idx]
    result["resistance_high"] = resistance_high_arr
    result["resistance_low"] = resistance_low_arr

    # ============================================================
    # 规则7：高量定三天 — 高量柱后观察窗口
    #  0 = 当天为高量日
    #  1-3 = 高量后第1-3天（观察窗口内）
    # >3 = 超出窗口
    # ============================================================
    days_arr = np.full(len(result), 999)
    last_high_vol_idx = -999
    for i in range(len(result)):
        if result["is_high_volume"].iloc[i]:
            last_high_vol_idx = i
        days_arr[i] = i - last_high_vol_idx
    result["days_since_high_vol"] = days_arr.astype(int)

    # ============================================================
    # 规则12/33：近20日高量柱次数
    # ============================================================
    hv_int = result["is_high_volume"].astype(int)
    result["high_vol_count_20d"] = hv_int.rolling(20, min_periods=1).sum().astype(int)

    # ============================================================
    # 规则19：下跌趋势确认 — 连续3根K线高低点方向
    # ============================================================
    trend_arr = np.full(len(result), "震荡", dtype=object)
    for i in range(2, len(result)):
        h0, h1, h2 = h.iloc[i], h.iloc[i - 1], h.iloc[i - 2]
        l0, l1, l2 = l.iloc[i], l.iloc[i - 1], l.iloc[i - 2]
        if h0 < h1 < h2 and l0 < l1 < l2:
            trend_arr[i] = "下跌"
        elif h0 > h1 > h2 and l0 > l1 > l2:
            trend_arr[i] = "上涨"
        else:
            trend_arr[i] = "震荡"
    result["trend_3bar"] = trend_arr

    # ============================================================
    # 规则27/30辅助：连续阳线/阴线根数
    # ============================================================
    yang_arr = np.zeros(len(result), dtype=int)
    yin_arr = np.zeros(len(result), dtype=int)
    for i in range(len(result)):
        if i == 0:
            yang_arr[i] = 1 if result["body_direction"].iloc[i] > 0 else 0
            yin_arr[i] = 1 if result["body_direction"].iloc[i] < 0 else 0
        else:
            if result["body_direction"].iloc[i] > 0:
                yang_arr[i] = yang_arr[i - 1] + 1
                yin_arr[i] = 0
            elif result["body_direction"].iloc[i] < 0:
                yin_arr[i] = yin_arr[i - 1] + 1
                yang_arr[i] = 0
            else:
                yang_arr[i] = 0
                yin_arr[i] = 0
    result["consecutive_yang"] = yang_arr
    result["consecutive_yin"] = yin_arr

    # ============================================================
    # 规则30：绿三兵 — 连续3天收盘价递减+阴线实体
    # ============================================================
    g3s_arr = np.zeros(len(result), dtype=bool)
    for i in range(2, len(result)):
        c0, c1, c2 = c.iloc[i], c.iloc[i-1], c.iloc[i-2]
        price_declining = c0 < c1 < c2
        all_bearish = (result["body_direction"].iloc[i] < 0 and
                       result["body_direction"].iloc[i-1] < 0 and
                       result["body_direction"].iloc[i-2] < 0)
        g3s_arr[i] = price_declining and all_bearish
    result["green_three_soldiers"] = g3s_arr

    # ============================================================
    # 规则20/26辅助：顶底分型检测
    # ============================================================
    # 底分型：中间K线最低，两边走高
    bottom_fx = np.zeros(len(result), dtype=bool)
    top_fx = np.zeros(len(result), dtype=bool)
    for i in range(2, len(result)):
        h0, h1, h2 = h.iloc[i], h.iloc[i-1], h.iloc[i-2]
        l0, l1, l2 = l.iloc[i], l.iloc[i-1], l.iloc[i-2]
        bottom_fx[i] = (l1 < l0) and (l1 < l2) and (h0 > h1 or h2 > h1)
        top_fx[i] = (h1 > h0) and (h1 > h2) and (l0 < l1 or l2 < l1)
    result["bottom_fractal"] = bottom_fx
    result["top_fractal"] = top_fx

    # ============================================================
    # 威科夫信号（精简版，只保留阶段判断关键信号）
    # ============================================================

    chg_pct = c.pct_change()

    # SC (Selling Climax / 恐慌抛售): 高量 + 大跌(>5%) + 日内明显反弹
    # 关键不是下影线长度，而是收盘价明显高于最低价=盘中恐慌盘被接走
    result["is_SC"] = (
        result["is_high_volume"] &
        (chg_pct < -0.05) &
        (c > l + 0.35 * amplitude)  # 收盘回到振幅35%以上位置=有承接
    )

    # BC (Buying Climax / 抢购高潮): 高量 + 长上影 + 冲高回落，且价格处于阶段高位
    price_rank_20d = c.rolling(20, min_periods=5).apply(lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min() + 0.001))
    result["is_BC"] = (
        result["is_high_volume"] &
        (result["upper_shadow_ratio"] > 0.30) &
        (c < h - 0.35 * amplitude) &
        (price_rank_20d > 0.70)  # 价格处于近20日高位
    )

    # ST (Secondary Test / 二次测试): SC后，价格回踩SC低点附近+缩量+不有效跌破
    st_arr = np.zeros(len(result), dtype=bool)
    sc_low = np.nan
    sc_vol = np.nan
    sc_close = np.nan
    for i in range(len(result)):
        if result["is_SC"].iloc[i]:
            sc_low = l.iloc[i]
            sc_vol = v.iloc[i]
            sc_close = c.iloc[i]
        if not np.isnan(sc_low) and not result["is_SC"].iloc[i]:
            near_sc = abs(l.iloc[i] - sc_low) / sc_low < 0.05  # 5%容差
            vol_shrink = v.iloc[i] < sc_vol * 0.8  # 量明显小于SC当日
            not_broken = c.iloc[i] > sc_low * 0.98  # 收盘不有效跌破SC低点
            st_arr[i] = near_sc and vol_shrink and not_broken
    result["is_ST"] = st_arr

    has_support = result["support_level"].notna()

    # Spring (震仓): SC之后出现，盘中跌破支撑但收盘收回（与规则29互补）
    spring_arr = np.zeros(len(result), dtype=bool)
    for i in range(len(result)):
        if has_support.iloc[i] and result["is_SC"].iloc[:i+1].any():
            spring_arr[i] = (l.iloc[i] < result["support_level"].iloc[i]) and (c.iloc[i] > result["support_level"].iloc[i])
    result["is_spring"] = spring_arr

    # SOW (Sign of Weakness / 弱势信号): 高量有效跌破关键支撑
    result["is_SOW"] = (
        has_support &
        (c < result["support_level"] * 0.98) &  # 收盘有效跌破支撑(>2%)
        (result["is_high_volume"])
    )

    # ============================================================
    # MACD（用于8项清单第⑥项：绿柱趋势判断）
    # ============================================================
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    result["macd_dif"] = ema12 - ema26
    result["macd_dea"] = result["macd_dif"].ewm(span=9, adjust=False).mean()
    result["macd_hist"] = result["macd_dif"] - result["macd_dea"]  # 柱=2*(DIF-DEA)的近似，正值多头负值空头
    # 柱趋势：连续3日柱值的变化方向
    hist = result["macd_hist"]
    result["macd_hist_trend"] = "持平"
    for i in range(3, len(result)):
        if hist.iloc[i] < hist.iloc[i-1] < hist.iloc[i-2]:
            result.iloc[i, result.columns.get_loc("macd_hist_trend")] = "放大（空头增强）" if hist.iloc[i] < 0 else "缩窄（多头减弱）"
        elif hist.iloc[i] > hist.iloc[i-1] > hist.iloc[i-2]:
            result.iloc[i, result.columns.get_loc("macd_hist_trend")] = "缩窄（空头减弱）" if hist.iloc[i] < 0 else "放大（多头增强）"
        elif hist.iloc[i] > hist.iloc[i-2]:
            result.iloc[i, result.columns.get_loc("macd_hist_trend")] = "收窄中" if hist.iloc[i] < 0 else "扩张中"
        else:
            result.iloc[i, result.columns.get_loc("macd_hist_trend")] = "扩张中" if hist.iloc[i] < 0 else "收窄中"

    # ============================================================
    # 市场状态
    # ============================================================
    result["market_state"] = market_state if market_state else "未知"

    return result


def evaluate_rules(facts_df: pd.DataFrame, lookback: int = 15) -> list[dict]:
    """
    程序化评估39条规则触发状态，返回已触发的规则列表。

    只评估最近 lookback 天内触发的规则。每条返回包含 id/name/decision/reasoning。
    对条件不满足的规则不返回——LLM 不再自行判断规则触发。
    """
    df = facts_df.copy()
    n = len(df)
    if n < 4:
        return []

    latest = df.iloc[-1]
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
    idx = df.index

    triggered = []

    def _last_date(pos: int = -1) -> str:
        d = idx[pos]
        return str(d.date()) if hasattr(d, "date") else str(d)[:10]

    def _near(price: float, level: float, tol: float = 0.03) -> bool:
        """价格是否在某个价位附近（±tol范围内）"""
        if pd.isna(level) or level <= 0:
            return False
        return abs(price - level) / level < tol

    def _above(price: float, level: float) -> bool:
        return (not pd.isna(level)) and level > 0 and price > level

    def _below(price: float, level: float) -> bool:
        return (not pd.isna(level)) and level > 0 and price < level

    # ================================================================
    # 规则1: 高量定义 — 当日量 > 前3日每一天的量
    # ================================================================
    if latest["is_high_volume"]:
        triggered.append({
            "id": 1, "name": "高量定义",
            "decision": "标记高量柱",
            "reasoning": f"{_last_date()}量能>前3日每一天的量，为绝对突出高量柱"
        })

    # ================================================================
    # 规则2: 高量拐点 — 出现高量柱
    # ================================================================
    if latest["is_high_volume"]:
        triggered.append({
            "id": 2, "name": "高量拐点",
            "decision": "拐点预警",
            "reasoning": f"{_last_date()}出现高量柱，收{c.iloc[-1]:.2f}，跌{((c.iloc[-1]/c.iloc[-2]-1)*100):+.2f}%。任何高量都意味着当前趋势可能被打破，需观察后续3天走势"
        })

    # ================================================================
    # 规则6: 非高量下影线 — 下影线但非高量
    # ================================================================
    if not latest["is_high_volume"] and latest["lower_shadow_ratio"] > 0.30:
        triggered.append({
            "id": 6, "name": "非高量下影线",
            "decision": "风险回避",
            "reasoning": f"{_last_date()}下影{latest['lower_shadow_ratio']:.0%}但非高量，非高量下影线=风险信号"
        })

    # ================================================================
    # 规则9: 假阴假阳 — K线颜色与实际涨跌方向背离
    # ================================================================
    for i in range(max(0, n - 5), n):
        if df["is_fake"].iloc[i]:
            d = _last_date(i)
            triggered.append({
                "id": 9, "name": "假阴假阳",
                "decision": "观望",
                "reasoning": f"{d}出现假K线（K线颜色与实际涨跌方向背离），多空分歧大"
            })
            break  # 最近一次即可

    # ================================================================
    # 规则10: 梯量 — 连续3日量增价涨（上涨梯量）或 连续3日量缩价跌（下跌梯量）
    # ================================================================
    for i in range(max(0, n - 5), n):
        if i < 2:
            continue
        v0, v1, v2 = v.iloc[i-2], v.iloc[i-1], v.iloc[i]
        c0, c1, c2 = c.iloc[i-2], c.iloc[i-1], c.iloc[i]
        if v2 > v1 > v0 and c2 > c1 > c0:
            triggered.append({
                "id": 10, "name": "梯量（上涨梯量）",
                "decision": "减仓",
                "reasoning": f"{_last_date(i-2)}→{_last_date(i)}连续3日量增价涨，量能透支，上涨末端预警"
            })
            break
        if v2 < v1 < v0 and c2 < c1 < c0:
            triggered.append({
                "id": 10, "name": "梯量（下跌梯量）",
                "decision": "机会进场",
                "reasoning": f"{_last_date(i-2)}→{_last_date(i)}连续3日量缩价跌，量能衰竭，机会临近"
            })
            break

    # ================================================================
    # 规则12: 下跌三次高量 — 下跌趋势中近20日≥3次高量
    # ================================================================
    recent_trend = df["trend_3bar"].iloc[-5:]
    is_downtrend = (recent_trend == "下跌").sum() >= 2
    if is_downtrend and latest["high_vol_count_20d"] >= 3:
        triggered.append({
            "id": 12, "name": "下跌三次高量",
            "decision": "机会进场",
            "reasoning": f"近20日出现{int(latest['high_vol_count_20d'])}次高量柱，下跌趋势中多次放量换手，抛压衰竭可择机布局"
        })

    # ================================================================
    # 规则13: 高量后缩量大长腿 — 高量后3天内缩量+下影线≥实体2倍
    # ================================================================
    for i in range(max(0, n - 5), n):
        days_since = df["days_since_high_vol"].iloc[i]
        if 1 <= days_since <= 3 and df["volume_state"].iloc[i] in ("缩量", "地量"):
            ls_ratio = df["lower_shadow_ratio"].iloc[i]
            body_ratio = df["body_ratio"].iloc[i]
            if ls_ratio > body_ratio * 1.5 and ls_ratio > 0.25:
                triggered.append({
                    "id": 13, "name": "高量后缩量大长腿",
                    "decision": "观望",
                    "reasoning": f"{_last_date(i)}高量后第{days_since}天，缩量+下影{ls_ratio:.0%}，分歧信号等待方向"
                })
                break

    # ================================================================
    # 规则15: 上影线触压 — 长上影+价格触及压力位
    # ================================================================
    for i in range(max(0, n - 5), n):
        if df["upper_shadow_ratio"].iloc[i] > 0.30:
            res_h = df["resistance_high"].iloc[i]
            if not pd.isna(res_h) and _near(h.iloc[i], res_h, 0.03):
                triggered.append({
                    "id": 15, "name": "上影线触压",
                    "decision": "减仓",
                    "reasoning": f"{_last_date(i)}上影{df['upper_shadow_ratio'].iloc[i]:.0%}触及压力{res_h:.2f}回落，压力位承压"
                })
                break

    # ================================================================
    # 规则16: 下跌无量反弹 — 下跌趋势中缩量/平量小幅反弹
    # ================================================================
    for i in range(max(0, n - 5), n):
        if i == 0:
            continue
        chg = (c.iloc[i] / c.iloc[i-1] - 1)
        if (df["trend_3bar"].iloc[i] == "下跌" and
            df["volume_state"].iloc[i] in ("缩量", "平量") and
            0 < chg < 0.03):
            triggered.append({
                "id": 16, "name": "下跌无量反弹",
                "decision": "观望",
                "reasoning": f"{_last_date(i)}{chg:+.1%}缩量/平量反弹，无量反弹无持续性，不追涨"
            })
            break

    # ================================================================
    # 规则17: 下跌首次高量 — 下跌趋势中第一次高量柱
    # ================================================================
    if latest["is_high_volume"] and latest["trend_3bar"] == "下跌":
        hv_count = df["is_high_volume"].iloc[-10:].sum()
        if hv_count <= 2:  # 近期高量少
            triggered.append({
                "id": 17, "name": "下跌首次高量",
                "decision": "观望3天",
                "reasoning": f"{_last_date()}下跌趋势中高量柱（近10日第{int(hv_count)}次），首次高量多诱多反弹，不急于抄底"
            })

    # ================================================================
    # 规则19: 下跌趋势确认 — 连续3根K线高低点下移
    # ================================================================
    if latest["trend_3bar"] == "下跌":
        # 确认最近3根的具体数据
        h3, h2, h1 = h.iloc[-3], h.iloc[-2], h.iloc[-1]
        l3, l2, l1 = l.iloc[-3], l.iloc[-2], l.iloc[-1]
        if h1 < h2 < h3 and l1 < l2 < l3:
            triggered.append({
                "id": 19, "name": "下跌趋势确认",
                "decision": "严控仓位",
                "reasoning": f"{_last_date(-3)}高点{h3:.2f} > {_last_date(-2)}高点{h2:.2f} > {_last_date()}高点{h1:.2f}，波峰波谷同步下移，空头完全主导"
            })

    # ================================================================
    # 规则20: 支撑底分型 — 支撑位附近形成底分型，且信号未过期（当前价未远离）
    # ================================================================
    for i in range(max(0, n - 3), n):
        if i < 2:
            continue
        if df["bottom_fractal"].iloc[i]:
            center_low = l.iloc[i - 1]  # 底分型中心K线低点，而非确认K线
            sup = df["support_level"].iloc[i]
            current_close = c.iloc[-1]
            if not pd.isna(sup) and _near(center_low, sup, 0.05):
                # 信号未过期：当前价不能远离支撑（<8%），否则已涨上去信号失效
                if _near(current_close, sup, 0.08):
                    center_date = _last_date(i - 1)
                    triggered.append({
                        "id": 20, "name": "支撑底分型",
                        "decision": "加仓",
                        "reasoning": f"{center_date}在支撑{sup:.2f}附近形成底分型（中心低{center_low:.2f}），支撑位企稳信号"
                    })
                    break

    # ================================================================
    # 规则21: 缩量下影后收阴 — 前日缩量下影+次日收阴
    # ================================================================
    for i in range(max(0, n - 4), n - 1):
        prev_vol = df["volume_state"].iloc[i]
        prev_ls = df["lower_shadow_ratio"].iloc[i]
        next_dir = df["body_direction"].iloc[i + 1]
        if prev_vol in ("缩量", "地量") and prev_ls > 0.25 and next_dir < 0:
            triggered.append({
                "id": 21, "name": "缩量下影后收阴",
                "decision": "减仓",
                "reasoning": f"{_last_date(i)}缩量下影{prev_ls:.0%}试探→{_last_date(i+1)}收阴回落，下影试探失败抛压重来"
            })
            break

    # ================================================================
    # 规则22: 支撑红三兵 — 支撑线上方连续3根小幅递增阳线
    # ================================================================
    if n >= 3:
        last3 = df.iloc[-3:]
        sup = latest["support_level"]
        if not pd.isna(sup):
            all_yang = all(last3["body_direction"] > 0)
            prices_up = last3["close"].iloc[0] < last3["close"].iloc[1] < last3["close"].iloc[2]
            near_support = all(_above(row["close"], sup) and _near(row["low"], sup, 0.05) for _, row in last3.iterrows())
            if all_yang and prices_up and near_support:
                triggered.append({
                    "id": 22, "name": "支撑红三兵",
                    "decision": "加仓",
                    "reasoning": f"{_last_date(-2)}→{_last_date()}支撑{sup:.2f}上方连续3阳，企稳小阳上攻"
                })

    # ================================================================
    # 规则23: 上天入地 — 影线长度超过实体2倍
    # ================================================================
    for i in range(max(0, n - 5), n):
        total_shadow = df["lower_shadow_ratio"].iloc[i] + df["upper_shadow_ratio"].iloc[i]
        body_r = df["body_ratio"].iloc[i]
        if body_r > 0 and total_shadow > body_r * 2:
            triggered.append({
                "id": 23, "name": "上天入地",
                "decision": "观望",
                "reasoning": f"{_last_date(i)}影线{total_shadow:.0%}超实体{body_r:.0%}的2倍，多空博弈剧烈等待方向"
            })
            break

    # ================================================================
    # 规则24: 阳线突破上影压力 — 前期长上影压力被阳线实体突破
    # ================================================================
    for i in range(max(0, n - 5), n):
        if df["body_direction"].iloc[i] > 0 and df["volume_state"].iloc[i] == "放量":
            res_h = df["resistance_high"].iloc[i]
            if not pd.isna(res_h) and c.iloc[i] > res_h * 1.01:
                triggered.append({
                    "id": 24, "name": "阳线突破上影压力",
                    "decision": "加仓",
                    "reasoning": f"{_last_date(i)}放量阳线突破压力{res_h:.2f}，压力变支撑，突破有效"
                })
                break

    # ================================================================
    # 规则25: 高量后高低点下移 — 高量柱后3天高低点持续下移
    # ================================================================
    for i in range(1, min(3, n - 0)):
        # 从高量日往后看3天
        pass  # 需要找到最近的高量日再往后看3天
    # 从最近高量日往后检查
    for hv_pos in range(n - 5, n):
        if hv_pos < 0:
            continue
        if df["is_high_volume"].iloc[hv_pos]:
            end_pos = min(hv_pos + 4, n)
            if end_pos - hv_pos >= 3 and end_pos <= n:
                sub = df.iloc[hv_pos:end_pos]
                sub_h = sub["high"].values
                sub_l = sub["low"].values
                if len(sub_h) >= 3 and all(sub_h[i] < sub_h[i-1] for i in range(1, len(sub_h))):
                    if all(sub_l[i] < sub_l[i-1] for i in range(1, len(sub_l))):
                        triggered.append({
                            "id": 25, "name": "高量后高低点下移",
                            "decision": "减仓",
                            "reasoning": f"{_last_date(hv_pos)}高量后{end_pos-hv_pos-1}天高低点持续下移，高量资金出逃"
                        })
                        break

    # ================================================================
    # 规则26: 压力线顶分型 — 压力位下方形成顶分型
    # ================================================================
    for i in range(max(0, n - 5), n):
        if df["top_fractal"].iloc[i]:
            res_h = df["resistance_high"].iloc[i]
            if not pd.isna(res_h) and _near(h.iloc[i], res_h, 0.05) and h.iloc[i] < res_h:
                triggered.append({
                    "id": 26, "name": "压力线顶分型",
                    "decision": "减仓",
                    "reasoning": f"{_last_date(i)}在压力位{res_h:.2f}附近形成顶分型，三次确认压力有效"
                })
                break

    # ================================================================
    # 规则27: 连阳后放量阴 — 连续≥4阳 + 放量/高量阴线
    # ================================================================
    for i in range(max(0, n - 5), n):
        yang_before = df["consecutive_yang"].iloc[i - 1] if i > 0 else 0
        if yang_before >= 4 and df["body_direction"].iloc[i] < 0:
            is_heavy = df["is_high_volume"].iloc[i] or df["volume_state"].iloc[i] == "放量"
            if is_heavy:
                triggered.append({
                    "id": 27, "name": "连阳后放量阴",
                    "decision": "减仓",
                    "reasoning": f"{_last_date(i-1)}之前连续{yang_before}阳，{_last_date(i)}"
                                 f"放量收阴（{((c.iloc[i]/c.iloc[i-1]-1)*100):+.1f}%），"
                                 f"累积获利盘涌出，放量阴线确认有人开始大规模兑现"
                })
                break

    # ================================================================
    # 规则28: 放量突破高量上影 — 前期高量上影被放量阳线突破
    # ================================================================
    for i in range(max(0, n - 5), n):
        if df["body_direction"].iloc[i] > 0 and df["volume_state"].iloc[i] == "放量":
            # 找前期有上影的高量柱
            for j in range(max(0, i - 20), i):
                if df["is_high_volume"].iloc[j] and df["upper_shadow_ratio"].iloc[j] > 0.20:
                    prev_high = h.iloc[j]
                    if c.iloc[i] > prev_high:
                        triggered.append({
                            "id": 28, "name": "放量突破高量上影",
                            "decision": "重仓跟进",
                            "reasoning": f"{_last_date(i)}放量阳线突破{_last_date(j)}高量上影高点{prev_high:.2f}，解放套牢盘上行空间打开"
                        })
                        break
            if any(r["id"] == 28 for r in triggered):
                break

    # ================================================================
    # 规则29: 高量破位后收回 — 高量跌破支撑+次日阳线收回
    # ================================================================
    for i in range(max(0, n - 4), n - 1):
        if df["is_high_volume"].iloc[i]:
            sup = df["support_level"].iloc[i]
            if not pd.isna(sup) and c.iloc[i] < sup * 0.98:
                if df["body_direction"].iloc[i + 1] > 0 and c.iloc[i + 1] > sup:
                    triggered.append({
                        "id": 29, "name": "高量破位后收回",
                        "decision": "观望",
                        "reasoning": f"{_last_date(i)}高量跌破支撑{sup:.2f}→{_last_date(i+1)}阳线收回，多空争夺观察后续"
                    })
                    break

    # ================================================================
    # 规则30: 压力线绿三兵 — 压力位下方出现绿三兵
    # ================================================================
    for i in range(max(0, n - 5), n):
        if df["green_three_soldiers"].iloc[i]:
            res_h = df["resistance_high"].iloc[i]
            if not pd.isna(res_h) and c.iloc[i] < res_h:
                triggered.append({
                    "id": 30, "name": "压力线绿三兵",
                    "decision": "清仓",
                    "reasoning": f"{_last_date(i-2)}至{_last_date(i)}连续3天收盘价递减（{c.iloc[i-2]:.2f}→{c.iloc[i-1]:.2f}→{c.iloc[i]:.2f}）且全部收阴，压力位{res_h:.2f}下方空头坚定推进"
                })
                break

    # ================================================================
    # 规则31: 地量≠地价 — 成交量持续地量
    # ================================================================
    recent_vol_state = df["volume_state"].iloc[-5:]
    if (recent_vol_state == "地量").sum() >= 3:
        triggered.append({
            "id": 31, "name": "地量≠地价",
            "decision": "观望",
            "reasoning": f"{_last_date(-4)}至{_last_date()}近5日{int((recent_vol_state=='地量').sum())}天地量，地量不等于地价，不盲目抄底"
        })

    # ================================================================
    # 规则32: 上涨高量大长腿 — 上涨趋势中高量+长上影
    # ================================================================
    for i in range(max(0, n - 5), n):
        if (df["is_high_volume"].iloc[i] and
            df["upper_shadow_ratio"].iloc[i] > 0.30 and
            df["trend_3bar"].iloc[i] == "上涨"):
            triggered.append({
                "id": 32, "name": "上涨高量大长腿",
                "decision": "减仓",
                "reasoning": f"{_last_date(i)}高量柱+上影{df['upper_shadow_ratio'].iloc[i]:.0%}，上涨趋势中途高位出现，盘中大幅回落，获利盘充裕，派发动机成立"
            })
            break

    # ================================================================
    # 规则33: 上涨三次高量 — 上涨趋势中近20日≥3次高量
    # ================================================================
    recent_trend_up = df["trend_3bar"].iloc[-5:]
    is_uptrend = (recent_trend_up == "上涨").sum() >= 2
    if is_uptrend and latest["high_vol_count_20d"] >= 3:
        triggered.append({
            "id": 33, "name": "上涨三次高量",
            "decision": "风险回避",
            "reasoning": f"近20日出现{int(latest['high_vol_count_20d'])}次高量柱，上涨趋势中多次放量换手，主力出货周期临近"
        })

    # ================================================================
    # 规则34: 连续三天高量 — 连续3天高量柱
    # ================================================================
    hv_arr = df["is_high_volume"].values
    for i in range(max(0, n - 5), n):
        if i >= 2 and hv_arr[i-2] and hv_arr[i-1] and hv_arr[i]:
            triggered.append({
                "id": 34, "name": "连续三天高量",
                "decision": "减仓",
                "reasoning": f"{_last_date(i-2)}至{_last_date(i)}连续3天均为高量柱，量能消耗不可持续，常出现在行情末端加速段"
            })
            break

    # ================================================================
    # 规则35: 高量第2-3天支撑线上 — 高量后2-3天运行在支撑线上
    # ================================================================
    for i in range(max(0, n - 5), n):
        days = df["days_since_high_vol"].iloc[i]
        if days in (2, 3):
            sup = df["support_level"].iloc[i]
            if not pd.isna(sup) and _above(c.iloc[i], sup):
                direction = "阳" if df["body_direction"].iloc[i] > 0 else "阴"
                decision = "持有" if direction == "阳" else "观望"
                triggered.append({
                    "id": 35, "name": "高量第2-3天支撑线上",
                    "decision": decision,
                    "reasoning": f"{_last_date(i)}高量后第{days}天，收{direction}线运行支撑{sup:.2f}上方，阳持阴观"
                })
                break

    # ================================================================
    # 规则36: 高量破位量能杂乱 — 高量破支撑+后续量能杂乱
    # ================================================================
    for hv_pos in range(n - 20, n - 2):
        if hv_pos < 0:
            continue
        if df["is_high_volume"].iloc[hv_pos]:
            sup = df["support_level"].iloc[hv_pos]
            if not pd.isna(sup):
                broke = False
                for k in range(hv_pos + 1, min(hv_pos + 6, n)):
                    if c.iloc[k] < sup * 0.98:
                        broke = True
                        break
                if broke:
                    # 检查后续量能是否杂乱——在破位后的几天内量能在放量/缩量/平量之间交替
                    post_vol = df["volume_state"].iloc[k:min(k+5, n)]
                    vol_types = set(post_vol)
                    if len(vol_types) >= 2:
                        triggered.append({
                            "id": 36, "name": "高量破位量能杂乱",
                            "decision": "清仓",
                            "reasoning": f"{_last_date(hv_pos)}高量（支撑{sup:.2f}）→{_last_date(k)}跌破支撑（收{c.iloc[k]:.2f}）→后续量能{'+'.join(sorted(vol_types))}交替，温水煮青蛙式出货"
                        })
                        break

    # ================================================================
    # 规则37: 下引线风险 — 近期多根长下影
    # ================================================================
    recent_ls = df["lower_shadow_ratio"].iloc[-10:]
    long_ls_count = (recent_ls > 0.30).sum()
    if long_ls_count >= 3:
        triggered.append({
            "id": 37, "name": "下引线风险",
            "decision": "风险回避",
            "reasoning": f"近10日出现{int(long_ls_count)}根长下影线，下影线越多越长后续下跌概率越大，不要抄底"
        })

    # ================================================================
    # 规则38: 高位量大实体小 — 高位+高量+小实体
    # ================================================================
    for i in range(max(0, n - 5), n):
        if df["is_high_volume"].iloc[i] and df["body_ratio"].iloc[i] < 0.30:
            # 检查是否高位：价格处于近20日高位
            pos = max(0, i - 19)
            price_rank = (c.iloc[i] - c.iloc[pos:i+1].min()) / (c.iloc[pos:i+1].max() - c.iloc[pos:i+1].min() + 0.001)
            if price_rank > 0.70:
                triggered.append({
                    "id": 38, "name": "高位量大实体小",
                    "decision": "减仓",
                    "reasoning": f"{_last_date(i)}高量柱+实体仅{df['body_ratio'].iloc[i]:.0%}+上影{df['upper_shadow_ratio'].iloc[i]:.0%}（价格停滞+高量=隐蔽出货信号，有人暗中出货而接盘力量刚好抵消）"
                })
                break

    # 按规则ID排序
    triggered.sort(key=lambda x: x["id"])
    return triggered


def format_fact_text(facts_df: pd.DataFrame, lookback: int = 10) -> str:
    """
    将最近 N 天的事实 DataFrame 格式化为 LLM 可读文本

    每行格式：
    日期 | 收 | 涨跌% | 量能 | 高量 | 窗口 | 下影 | 上影 | 实体 |
    支撑 | 压力高 | 压力低 | 趋势 | 连阳 | 连阴 | 假K | 20日高量次数
    """
    df = facts_df.tail(lookback).copy()
    lines = []
    lines.append("日期       | 收盘价 | 涨跌%  | 量能 | 高量 | 窗口 | 下影% | 上影% | 实体% | 支撑   | 压力高 | 压力低 | 趋势 | 连阳/阴 | 假K | 绿三 | 20d高量")
    lines.append("-" * 120)

    for pos, (idx, row) in enumerate(df.iterrows()):
        date_str = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
        if pos > 0:
            prev_c = df.iloc[pos - 1]["close"]
            chg = f"{(row['close'] - prev_c) / prev_c * 100:+.2f}"
        else:
            chg = "---"

        hv = "★" if row["is_high_volume"] else " "
        fake = "假" if row["is_fake"] else " "
        window = row["days_since_high_vol"]
        window_str = str(window) if window <= 3 else "-"

        sup_str = f"{row['support_level']:>6.2f}" if not pd.isna(row["support_level"]) else "   ---"
        res_h = f"{row['resistance_high']:>6.2f}" if not pd.isna(row["resistance_high"]) else "   ---"
        res_l = f"{row['resistance_low']:>6.2f}" if not pd.isna(row["resistance_low"]) else "   ---"
        trend_icon = {"上涨": "↑", "下跌": "↓", "震荡": "→"}.get(row["trend_3bar"], "?")
        yy = f"{row['consecutive_yang']}/{row['consecutive_yin']}"
        g3s = "G3" if row.get("green_three_soldiers", False) else "   "

        lines.append(
            f"{date_str} | {row['close']:>6.2f} | {chg:>6} | "
            f"{row['volume_state']:<4} | { hv }  | {window_str:>3} | "
            f"{row['lower_shadow_ratio']:.0%}  | {row['upper_shadow_ratio']:.0%}  | "
            f"{row['body_ratio']:.0%}  | {sup_str} | {res_h} | {res_l} | "
            f"{trend_icon:<3} | {yy:<6} | {fake:<3} | {g3s} | {row['high_vol_count_20d']:>3}"
        )

    return "\n".join(lines)
