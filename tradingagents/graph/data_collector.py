"""DataCollector: fetch all data once, serve windowed views to analyst agents."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import threading
import time
import pandas as pd
from stockstats import wrap
import io

from tradingagents.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_global_news,
    get_insider_transactions,
    get_board_fund_flow,
    get_individual_fund_flow,
    get_lhb_detail,
    get_zt_pool,
    get_hot_stocks_xq,
    get_hsgt_individual,
    get_hsgt_flow,
    get_margin_detail,
    get_block_trades,
    get_lhb_institution_stats,
    get_lhb_active_seats,
    get_research_reports,
    get_shareholder_changes,
    get_restricted_release,
    get_pledge_ratio,
    get_shareholder_count,
    get_dividend_history,
    get_concept_board,
    get_individual_fund_flow_120d,
    get_five_level_orderbook,
    get_f10_detail,
    get_level2_quotes,
    get_cninfo_announcements,
)

INDICATORS = [
    "close_50_sma", "close_200_sma", "close_10_ema",
    "rsi", "macd", "boll", "boll_ub", "boll_lb", "atr", "vwma",
]
SHORT_DAYS = 14
LONG_DAYS = 90

import numpy as np

_OHLCV_COLS = ["date", "open", "high", "low", "close", "volume"]


def _parse_csv_to_dataframe(raw_csv: str) -> Optional[pd.DataFrame]:
    """Parse raw CSV string into a normalized OHLCV DataFrame.

    Returns None if parsing fails or the CSV is too short/empty.
    """
    if not isinstance(raw_csv, str) or len(raw_csv) <= 50:
        return None
    try:
        df = pd.read_csv(io.StringIO(raw_csv), on_bad_lines='skip', comment='#')
    except Exception:
        return None
    if df.empty:
        return None
    cols_map = {c.lower(): c for c in df.columns}
    rename_dict = {}
    for target in _OHLCV_COLS:
        if target in cols_map:
            rename_dict[cols_map[target]] = target
    df = df.rename(columns=rename_dict)
    return df


# ── VPA (Volume Price Analysis) 预计算 ──────────────────────────


def _compute_vpa_indicators(df: pd.DataFrame, window: int = 20) -> str:
    """Pre-compute Volume Price Analysis indicators from OHLCV DataFrame.

    Returns a human-readable text block for the VPA analyst agent.
    Three layers of pre-digestion:
    1. Standardized labels per bar (volume level / body size / shadow level)
    2. Auto-detection of 9 classic VPA patterns
    3. Pattern summary table — LLM interprets meaning, not raw numbers
    """
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(set(df.columns)):
        return "VPA 数据不足：缺少 OHLCV 列"

    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df["open"] = pd.to_numeric(df["open"], errors="coerce")
    df["high"] = pd.to_numeric(df["high"], errors="coerce")
    df["low"] = pd.to_numeric(df["low"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])

    if len(df) < window + 5:
        return "VPA 数据不足：历史 K 线数量不够"

    # ── 派生指标 ──
    df["vol_ma"] = df["volume"].rolling(window).mean()
    df["volume_ratio"] = df["volume"] / df["vol_ma"]

    hl_range = df["high"] - df["low"]
    df["bar_spread"] = hl_range / df["close"]  # 振幅（含影线）
    body = (df["close"] - df["open"]).abs()
    df["body_ratio"] = body / df["close"]       # 实体相对大小
    df["close_position"] = np.where(
        hl_range > 0,
        (df["close"] - df["low"]) / hl_range,
        0.5,
    )
    df["bar_type"] = np.where(
        df["close"] > df["open"], "阳线",
        np.where(df["close"] < df["open"], "阴线", "十字星"),
    )

    # 上下影线比例
    df["upper_shadow"] = np.where(
        hl_range > 0,
        (df["high"] - np.maximum(df["open"], df["close"])) / hl_range,
        0.0,
    )
    df["lower_shadow"] = np.where(
        hl_range > 0,
        (np.minimum(df["open"], df["close"]) - df["low"]) / hl_range,
        0.0,
    )

    # 价格变化率
    df["pct_change"] = df["close"].pct_change()

    # 量能趋势 (5日均量 vs 20日均量)
    df["vol_ma5"] = df["volume"].rolling(5).mean()
    df["vol_trend_ratio"] = df["vol_ma5"] / df["vol_ma"]

    # 量价一致性
    df["vp_harmony"] = np.where(
        (df["pct_change"] > 0) & (df["volume_ratio"] > 1.0), "一致(涨+放量)",
        np.where(
            (df["pct_change"] < 0) & (df["volume_ratio"] > 1.0), "一致(跌+放量)",
            np.where(
                (df["pct_change"] > 0) & (df["volume_ratio"] < 0.8), "背离(涨+缩量)",
                np.where(
                    (df["pct_change"] < 0) & (df["volume_ratio"] < 0.8), "背离(跌+缩量)",
                    "中性",
                ),
            ),
        ),
    )

    # OBV (On Balance Volume) 简易趋势 — vectorized
    close_diff = df["close"].diff()
    obv_sign = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
    obv_sign[0] = 0
    df["obv"] = (obv_sign * df["volume"].values).cumsum()
    obv_ma = df["obv"].rolling(10).mean()
    obv_trend = "上升" if len(obv_ma.dropna()) >= 2 and obv_ma.iloc[-1] > obv_ma.iloc[-5] else "下降"

    # 近10日最高/最低收盘价（用于判断趋势位置）
    df["close_10d_high"] = df["close"].rolling(10).max()
    df["close_10d_low"] = df["close"].rolling(10).min()
    df["close_pct_rank"] = np.where(
        (df["close_10d_high"] - df["close_10d_low"]) > 0,
        (df["close"] - df["close_10d_low"]) / (df["close_10d_high"] - df["close_10d_low"]),
        0.5,
    )

    # ── 1. 标准化标签函数 ──
    def vol_level(vr):
        if vr > 2.5:    return "极高", 3
        elif vr > 1.5:  return "高放量", 2
        elif vr > 1.0:  return "温和放量", 1
        elif vr > 0.8:  return "均量", 0
        elif vr > 0.5:  return "缩量", -1
        else:           return "极度缩量", -2

    def body_level(br):
        if br > 0.03:   return "大实体", 3
        elif br > 0.015: return "中实体", 2
        elif br > 0.005: return "小实体", 1
        else:            return "十字星", 0

    # ── 2. 经典形态自动识别（逐日） ──
    def detect_patterns(row):
        """Return list of (pattern_name, confidence, theory_ref) tuples."""
        patterns = []
        vr = row["volume_ratio"] if pd.notna(row["volume_ratio"]) else 1.0
        us = row["upper_shadow"]
        ls = row["lower_shadow"]
        br = row["body_ratio"]
        bt = row["bar_type"]
        cp = row["close_position"]
        pct = row["pct_change"] if pd.notna(row["pct_change"]) else 0
        cr = row["close_pct_rank"] if pd.notna(row["close_pct_rank"]) else 0.5

        # 吊人线：锤头形态但出现在高位 — 必须先于锤头线检查（条件更严格）
        if ls > 0.6 and cp > 0.65 and cr > 0.65:
            conf = "高" if vr > 1.5 else "中"
            patterns.append((f"吊人线({conf})", f"长下影{ls:.0%}+收盘高位{cp:.0%}+高位({cr:.0%})", ["顶部警告", "弱势隐现"]))
        # 锤头线：长下影 + 收盘高位 + 中低位（非高位）
        elif ls > 0.6 and cp > 0.65:
            conf = "高" if vr > 1.5 else "中"
            ctx = "下跌途中" if cr < 0.3 else "低位"
            patterns.append((f"锤头线({conf})", f"长下影{ls:.0%}+收盘高位{cp:.0%}+{ctx}", ["底部反转", "强势"]))
        # 射击十字星：长上影 + 小实体 + 收盘在中低位
        if us > 0.6 and br < 0.02 and cp < 0.5:
            conf = "高" if vr > 1.5 else "中"
            patterns.append((f"射击十字星({conf})", f"长上影{us:.0%}+小实体{br:.1%}+收盘低位{cp:.0%}", ["顶部反转", "弱势"]))
        # 长腿十字线：双影都长 + 极窄实体
        if us > 0.35 and ls > 0.35 and br < 0.01:
            conf = "高" if vr > 1.5 else "中"
            patterns.append((f"长腿十字线({conf})", f"上影{us:.0%}+下影{ls:.0%}+实体{br:.1%}", ["方向不明", "震仓疑似" if vr < 0.8 else "多空激战"]))
        # 放量滞涨：高量 + 极窄实体 + 价格几乎不动
        if vr > 1.8 and br < 0.015 and abs(pct) < 0.015:
            patterns.append(("放量滞涨", f"量比{vr:.1f}+振幅{br:.1%}+涨跌{pct:+.2%}", ["派发信号", "多空分歧大"]))
        # 卖出高潮(Selling Climax)：急跌 + 巨量 + 收盘收回过半
        if pct < -0.03 and vr > 2.0 and cp > 0.5:
            patterns.append(("卖出高潮(Selling Climax)", f"跌{pct:+.1%}+量比{vr:.1f}+收盘收回{cp:.0%}", ["恐慌见底", "买入高峰临近"]))
        # 买入高潮(Buying Climax)：急涨 + 巨量 + 上影
        if pct > 0.03 and vr > 2.0 and us > 0.3:
            patterns.append(("买入高潮(Buying Climax)", f"涨{pct:+.1%}+量比{vr:.1f}+上影{us:.0%}", ["派发尾声", "抛售高峰临近"]))
        # 高实体低量异常：大实体 + 低量 = 陷阱
        if br > 0.03 and vr < 0.8:
            patterns.append(("高实体低量异常", f"实体{br:.1%}+量比{vr:.1f}", ["虚假走势", "局内人未参与"]))
        # 低实体高量异常：小实体 + 高量 = 拉锯
        if 0.005 < br < 0.015 and vr > 1.5:
            tag = "牛市力竭" if bt == "阳线" else "熊转牛信号"
            patterns.append(("低实体高量异常", f"实体{br:.1%}+量比{vr:.1f}+{tag}", ["趋势可能反转"]))
        return patterns

    # ── 格式化输出（取最近 N 天）──
    output_days = min(30, len(df) - window)
    recent = df.tail(output_days).copy()

    lines = []

    # ── 量能概况 ──
    last = recent.iloc[-1]
    vol_5d = recent["volume"].tail(5).mean()
    vol_20d = last["vol_ma"] if pd.notna(last["vol_ma"]) else 0
    vol_summary = "放量" if vol_5d > vol_20d * 1.2 else ("缩量" if vol_5d < vol_20d * 0.8 else "平稳")
    obv_5d_change = "加速上升" if obv_trend == "上升" and len(recent) >= 5 and recent["obv"].iloc[-1] - recent["obv"].iloc[-5] > recent["obv"].iloc[-5] * 0.1 else obv_trend

    lines.append(f"## VPA 预计算指标（{window}日均量基准）\n")
    _mtf_slot = len(lines)  # 大周期定调占位，多周期计算完成后回填
    lines.append("")
    lines.append("### 量能概况\n")
    lines.append(f"| 指标 | 数值 | 级别 |")
    lines.append(f"|------|------|------|")
    lines.append(f"| 近5日量能趋势 | 5日/20日均量={last.get('vol_trend_ratio', 0):.2f} | **{vol_summary}** |")
    lines.append(f"| OBV趋势(10日) | — | **{obv_5d_change}** |")

    # 近5日量价背离
    last5 = recent.tail(5)
    p5_start, p5_end = last5["close"].iloc[0], last5["close"].iloc[-1]
    v5_start, v5_end = last5["volume"].iloc[0], last5["volume"].iloc[-1]
    p5_dir = "涨" if p5_end > p5_start else "跌"
    v5_dir = "放量" if v5_end > v5_start * 1.2 else ("缩量" if v5_end < v5_start * 0.8 else "平稳")
    p5_v5 = "一致" if (p5_dir == "涨" and v5_dir == "放量") or (p5_dir == "跌" and v5_dir == "缩量") else ("背离" if v5_dir != "平稳" else "中性")
    if p5_v5 == "背离":
        lines.append(f"| [!] 近5日量价关系 | 价格{p5_dir}+量能{v5_dir} | **背离** |")
    else:
        lines.append(f"| 近5日量价关系 | 价格{p5_dir}+量能{v5_dir} | {p5_v5} |")

    # 价格位置（10日）
    cr_last = last["close_pct_rank"] if pd.notna(last["close_pct_rank"]) else 0.5
    pos_label = "高位" if cr_last > 0.7 else ("低位" if cr_last < 0.3 else "中位")
    lines.append(f"| 10日价格位置 | 排名{cr_last:.0%} | **{pos_label}** |\n")

    # ── 3. 逐日数据表（带标准标签） ──
    lines.append("### 逐日量价数据\n")
    lines.append("| 日期 | K线 | 涨跌 | 实体 | 收盘 | 上影 | 下影 | 量级 | 量比 | 价量关系 | 识别形态 |")
    lines.append("|------|-----|------|------|------|------|------|------|------|----------|----------|")

    all_patterns = []  # collect all detected patterns for summary

    for _, row in recent.iterrows():
        dt = row.get("date", "")
        if hasattr(dt, "strftime"):
            dt = dt.strftime("%m-%d")
        else:
            dt = str(dt)[-5:]

        pct = row["pct_change"] * 100 if pd.notna(row["pct_change"]) else 0
        br = row["body_ratio"] if pd.notna(row["body_ratio"]) else 0
        body_label, _ = body_level(br)
        cp = row["close_position"] if pd.notna(row["close_position"]) else 0.5
        cp_label = "高位" if cp > 0.7 else ("低位" if cp < 0.3 else "中位")
        vr = row["volume_ratio"] if pd.notna(row["volume_ratio"]) else 1.0
        vl, _ = vol_level(vr)
        us_val = row["upper_shadow"] if pd.notna(row["upper_shadow"]) else 0
        ls_val = row["lower_shadow"] if pd.notna(row["lower_shadow"]) else 0

        # 检测形态
        patterns = detect_patterns(row)
        pattern_str = "; ".join(p[0] for p in patterns) if patterns else "—"
        if patterns:
            all_patterns.append((dt, patterns, row.to_dict()))

        lines.append(
            f"| {dt} | {row['bar_type']} | {pct:+.1f}% | {body_label} | {cp_label}({cp:.0%}) "
            f"| {us_val:.0%} | {ls_val:.0%} "
            f"| **{vl}** | {vr:.1f} | {row['vp_harmony']} | {pattern_str} |"
        )

    # ── 4. 形态汇总表 ──
    lines.append("\n### 经典形态汇总\n")
    if all_patterns:
        lines.append("| 日期 | 形态名称 | 量级 | 形态特征 | 理论指向 |")
        lines.append("|------|----------|------|----------|----------|")
        for dt, patterns, rd in all_patterns:
            vr_val = rd.get("volume_ratio", 1.0) if isinstance(rd, dict) else 1.0
            vl, _ = vol_level(vr_val if pd.notna(vr_val) else 1.0)
            for p in patterns:
                name_raw, detail, theory = p
                theory_str = " → ".join(theory)
                lines.append(f"| {dt} | **{name_raw}** | {vl} | {detail} | {theory_str} |")
    else:
        lines.append("- 近期无经典量价形态触发\n")

    # ── 5. 趋势段拆解 ──
    lines.append("### 近期趋势结构\n")
    # 用简单规则将最近15根K线拆分为上涨段/下跌段/横盘段
    recent15 = recent.tail(15)
    segments = []
    if len(recent15) >= 3:
        current_dir = None
        seg_start = 0
        for i in range(1, len(recent15)):
            close_i = recent15["close"].iloc[i]
            close_prev = recent15["close"].iloc[i - 1]
            if close_i > close_prev * 1.005:
                direction = "up"
            elif close_i < close_prev * 0.995:
                direction = "down"
            else:
                direction = "flat"

            if direction != current_dir:
                if current_dir is not None and i - seg_start >= 2:
                    seg = recent15.iloc[seg_start:i]
                    dt_start = str(seg["date"].iloc[0])[-5:] if hasattr(seg["date"].iloc[0], "strftime") else str(seg["date"].iloc[0])[-5:]
                    dt_end = str(seg["date"].iloc[-1])[-5:] if hasattr(seg["date"].iloc[-1], "strftime") else str(seg["date"].iloc[-1])[-5:]
                    chg = (seg["close"].iloc[-1] - seg["close"].iloc[0]) / seg["close"].iloc[0] * 100
                    avg_vol = seg["volume"].mean()
                    vol_20d_ref = recent15["volume"].rolling(min(len(seg), 20)).mean().iloc[-1]
                    vol_status = "放量" if avg_vol > vol_20d_ref * 1.2 else ("缩量" if avg_vol < vol_20d_ref * 0.8 else "均量")
                    dir_label = {"up": "上涨", "down": "下跌", "flat": "横盘"}
                    segments.append(f"| {dt_start}~{dt_end} | {dir_label.get(current_dir, '—')} | {chg:+.1f}% | {vol_status} | {len(seg)}根 |")
                seg_start = i
                current_dir = direction

        if current_dir is not None and len(recent15) - seg_start >= 1:
            seg = recent15.iloc[seg_start:]
            dt_start = str(seg["date"].iloc[0])[-5:] if hasattr(seg["date"].iloc[0], "strftime") else str(seg["date"].iloc[0])[-5:]
            dt_end = str(seg["date"].iloc[-1])[-5:] if hasattr(seg["date"].iloc[-1], "strftime") else str(seg["date"].iloc[-1])[-5:]
            chg = (seg["close"].iloc[-1] - seg["close"].iloc[0]) / seg["close"].iloc[0] * 100
            avg_vol = seg["volume"].mean()
            vol_20d_ref = recent15["volume"].rolling(min(len(seg), 20)).mean().iloc[-1]
            vol_status = "放量" if avg_vol > vol_20d_ref * 1.2 else ("缩量" if avg_vol < vol_20d_ref * 0.8 else "均量")
            dir_label = {"up": "上涨", "down": "下跌", "flat": "横盘"}
            segments.append(f"| {dt_start}~{dt_end} | {dir_label.get(current_dir, '—')} | {chg:+.1f}% | {vol_status} | {len(seg)}根 |")

    if segments:
        lines.append("| 区间 | 方向 | 幅度 | 量能 | 持续 |")
        lines.append("|------|------|------|------|------|")
        lines.extend(segments)
    else:
        lines.append("- 数据不足以拆解趋势段\n")

    # ── 6. 多周期参照（周K/月K） ──
    lines.append("### 多周期参照\n")
    lines.append("以下将日线数据聚合为周K和月K，用于判断当前日线信号在大周期中的位置。\n")

    full_df = df.copy()
    if "date" in full_df.columns:
        full_df["date"] = pd.to_datetime(full_df["date"], errors="coerce")
        full_df = full_df.dropna(subset=["date"]).set_index("date").sort_index()
    else:
        full_df = full_df.assign(_dt=pd.to_datetime(full_df.index, errors="coerce")).set_index("_dt").sort_index()

    # 日线轨道线（用于未完成K线的趋势结构判断）
    full_df["ema5"] = full_df["close"].ewm(span=5, adjust=False).mean()
    full_df["ema39"] = full_df["close"].ewm(span=39, adjust=False).mean()

    def _resample_ohlcv(df_ohlc, rule, label):
        """Resample daily OHLCV to weekly/monthly bars.

        Weekly: A股自然周（周一至周五），节假日缩量也是完整一根，
        标签取该周最后一个实际交易日。
        """
        agg = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        available = {k: v for k, v in agg.items() if k in df_ohlc.columns}
        if len(available) < 5:
            return None

        if rule == "W-FRI":
            # 按 ISO 周号分组（自然周 Mon-Sun），标签用组内最后实际日期
            iso = df_ohlc.index.isocalendar()
            wk_key = list(zip(iso.year, iso.week))
            df_temp = df_ohlc.assign(_wk=wk_key)
            grouped = df_temp.groupby("_wk")
            resampled = grouped.agg(available)
            # 设置标签为每组最后一个实际交易日
            resampled.index = grouped["close"].apply(lambda x: x.index[-1])
            resampled = resampled.dropna()
            if len(resampled) < 3:
                return None
            return resampled
        else:
            resampled = df_ohlc.resample(rule).agg(available).dropna()
            if len(resampled) < 3:
                return None
            return resampled

    def _slope_trend(bars):
        """Return slope-sequence trend label for a bar series."""
        if bars is None or len(bars) < 3:
            return "不足"
        slopes = []
        for i in range(1, len(bars)):
            sl = (bars["close"].iloc[i] - bars["close"].iloc[i-1]) / bars["close"].iloc[i-1] * 100
            slopes.append(sl)
        # Decompose into same-direction runs
        runs = []
        i = 0
        while i < len(slopes):
            sign = 1 if slopes[i] > 0 else -1
            j = i
            while j < len(slopes) and (slopes[j] > 0) == (sign > 0):
                j += 1
            runs.append((sign, j - i))
            i = j
        cur_sign, cur_len = runs[-1]
        prev_sign, prev_len = runs[-2] if len(runs) >= 2 else (0, 0)
        if cur_sign < 0 and cur_len >= 3:
            return "持续下跌"
        if cur_sign > 0 and cur_len >= 3:
            return "持续上涨"
        if cur_sign > 0 and prev_sign < 0 and prev_len >= 3:
            return "止跌" if cur_len == 1 else "反弹"
        if cur_sign < 0 and prev_sign > 0 and prev_len >= 2:
            return "转弱"
        if cur_sign > 0 and cur_len >= 2:
            return "短线走强"
        if cur_sign < 0 and cur_len >= 2:
            return "短线走弱"
        recent3 = slopes[-3:] if len(slopes) >= 3 else slopes
        up_cnt = sum(1 for s in recent3 if s > 0)
        down_cnt = sum(1 for s in recent3 if s < 0)
        if down_cnt > up_cnt:
            return "震荡偏空"
        if up_cnt > down_cnt:
            return "震荡偏多"
        return "震荡"

    def _summarize_bars(bars, label, n):
        """Produce a compact summary for a higher timeframe."""
        if bars is None or len(bars) < 3:
            return [f"- **{label}**: 数据不足（需至少3根K线）"]
        lines_out = []
        # Trend direction from slope sequence (NOT first-vs-last)
        slope_dir = _slope_trend(bars)
        # Volume trend
        vol_first, vol_last = bars["volume"].iloc[:2].mean(), bars["volume"].iloc[-2:].mean()
        vol_dir = "放量" if vol_last > vol_first * 1.15 else ("缩量" if vol_last < vol_first * 0.85 else "平稳")
        # Recent high/low
        recent_high = bars["high"].max()
        recent_low = bars["low"].min()
        current_close = bars["close"].iloc[-1]
        pos_in_range = (current_close - recent_low) / (recent_high - recent_low) * 100 if recent_high > recent_low else 50
        # Moving averages
        bars_ma20 = bars["close"].rolling(min(3, len(bars))).mean().iloc[-1] if len(bars) >= 3 else current_close

        lines_out.append(f"**{label}趋势**（近{n}根）：{slope_dir} | 量能 {vol_dir}")
        lines_out.append(f"- 最高: {recent_high:.2f} | 最低: {recent_low:.2f} | 当前: {current_close:.2f} (区间位置 {pos_in_range:.0f}%)")
        if current_close > bars_ma20:
            lines_out.append(f"- 当前价位于{n}均线上方（均线 {bars_ma20:.2f}）→ 中期偏强")
        else:
            lines_out.append(f"- 当前价位于{n}均线下方（均线 {bars_ma20:.2f}）→ 中期偏弱")

        # Simple pattern: consecutive direction
        if len(bars) >= 3:
            last3 = bars.tail(3)
            up_count = sum(1 for i in range(1, len(last3)) if last3["close"].iloc[i] > last3["close"].iloc[i-1])
            down_count = len(last3) - 1 - up_count
            if up_count == len(last3) - 1:
                lines_out.append(f"- 最近{len(last3)}根{n}连续收阳 → 短期动能向上")
            elif down_count == len(last3) - 1:
                lines_out.append(f"- 最近{len(last3)}根{n}连续收阴 → 短期动能向下")
        return lines_out

    # Resample to weekly
    weekly_full = _resample_ohlcv(full_df, "W-FRI", "周K") if len(full_df) >= 25 else None
    if weekly_full is not None:
        lines.extend(_summarize_bars(weekly_full.tail(8), "周线", "周"))
    else:
        lines.append("- **周线**: 数据不足")

    # Resample to monthly
    monthly_full = _resample_ohlcv(full_df, "ME", "月K") if len(full_df) >= 60 else None
    if monthly_full is not None:
        lines.extend(_summarize_bars(monthly_full.tail(8), "月线", "月"))
    else:
        lines.append("- **月线**: 数据不足")

    # ── 多周期一致性校验（相邻K线斜率序列） ──
    w_dir = m_dir = "不足"
    w_r = m_r = 99
    partial = False

    lines.append("")
    lines.append("**多周期一致性**：")
    if weekly_full is not None and monthly_full is not None:

        def _consecutive_slopes(bars):
            """返回相邻K线的涨跌幅序列（百分比）"""
            prev = bars["close"].shift(1)
            return ((bars["close"] - prev) / prev * 100).dropna().tolist()

        def _analyze_slope_sequence(slopes, label):
            """按连续同向段(run)分析斜率序列，保留每个斜率在序列中的位置。"""
            if len(slopes) < 2:
                return f"{label}数据不足", "不足"

            # 将完整序列拆成连续同向段
            runs = []  # [(方向符号, 长度)]
            i = 0
            while i < len(slopes):
                sign = 1 if slopes[i] > 0 else -1
                j = i
                while j < len(slopes) and (slopes[j] > 0) == (sign > 0):
                    j += 1
                runs.append((sign, j - i))
                i = j

            cur_sign, cur_len = runs[-1]
            prev_sign, prev_len = runs[-2] if len(runs) >= 2 else (0, 0)

            # 符号序列展示整体走势
            seq_str = " → ".join("+" * r[1] if r[0] > 0 else "-" * r[1] for r in runs)

            if cur_sign < 0 and cur_len >= 3:
                if cur_len >= 4 and abs(slopes[-1]) < abs(slopes[-2]):
                    return f"{label}持续下跌但减速（{seq_str}，当前 {slopes[-1]:+.1f}%）", "下跌减速"
                return f"{label}持续下跌（{seq_str}，连跌{cur_len}根，当前 {slopes[-1]:+.1f}%）", "下跌"

            if cur_sign > 0 and cur_len >= 3:
                return f"{label}持续上涨（{seq_str}，当前 +{slopes[-1]:+.1f}%）", "上涨"

            # 前序长段反向 -> 转折信号
            if cur_sign > 0 and prev_sign < 0 and prev_len >= 3:
                if cur_len >= 2:
                    return f"{label}止跌后连涨（{seq_str}，此前连跌{prev_len}根，当前 +{slopes[-1]:+.1f}%）", "反弹"
                return f"{label}止跌企稳（{seq_str}，此前连跌{prev_len}根，本根转正 +{slopes[-1]:+.1f}%）", "止跌"
            if cur_sign < 0 and prev_sign > 0 and prev_len >= 2:
                return f"{label}涨势转弱（{seq_str}，此前连涨{prev_len}根，本根转负 {slopes[-1]:+.1f}%）", "转弱"

            if cur_sign > 0 and cur_len == 2 and prev_sign < 0:
                return f"{label}反弹启动（{seq_str}，此前连跌{prev_len}根，近{cur_len}根转正）", "反弹"
            if cur_sign < 0 and cur_len >= 2 and slopes[-1] < slopes[-2]:
                return f"{label}加速下跌（{seq_str}，连跌{cur_len}根，当前 {slopes[-1]:+.1f}%）", "加速下跌"

            # 幅度感知：前一根暴跌后本根转正 → 止跌（即使序列整体交替）
            if cur_sign > 0 and slopes[-2] < -5 and slopes[-1] < slopes[-2] * -0.5:
                return f"{label}暴跌后止跌（{seq_str}，前根 {slopes[-2]:+.1f}%，本根转正 +{slopes[-1]:+.1f}%）", "止跌"

            # 中间地带：2-3根同向，不到持续趋势但也不是纯震荡
            if cur_sign < 0 and cur_len >= 2:
                return f"{label}短线走弱（{seq_str}，连跌{cur_len}根）", "下跌"
            if cur_sign > 0 and cur_len >= 2:
                return f"{label}短线走强（{seq_str}，连涨{cur_len}根）", "反弹"

            # 纯震荡也带方向：看最近几根的偏多偏空
            recent3 = slopes[-3:] if len(slopes) >= 3 else slopes
            up_cnt = sum(1 for s in recent3 if s > 0)
            down_cnt = sum(1 for s in recent3 if s < 0)
            if down_cnt > up_cnt:
                return f"{label}震荡偏空（{seq_str}）", "震荡偏空"
            if up_cnt > down_cnt:
                return f"{label}震荡偏多（{seq_str}）", "震荡偏多"
            return f"{label}震荡（{seq_str}）", "震荡"

        def _dir_rank(d):
            """给方向一个强度排序值，用于对比"""
            order = {"上涨加速": 3, "上涨": 2, "反弹": 2, "震荡偏多": 1, "止跌": 1, "下跌减速": 0,
                     "震荡": 0, "震荡偏空": -1, "转弱": -1, "下跌": -2, "加速下跌": -2, "不足": 99}
            return order.get(d, 0)

        w_slopes = _consecutive_slopes(weekly_full.tail(9))   # 9根→8段斜率
        m_slopes = _consecutive_slopes(monthly_full.tail(7))  # 7根→6段斜率

        w_status, w_dir = _analyze_slope_sequence(w_slopes, "周线")
        m_status, m_dir = _analyze_slope_sequence(m_slopes, "月线")

        lines.append(f"- {w_status}")
        lines.append(f"- {m_status}")

        # ── 未完成K线的日內信号强度评估 ──
        today = pd.Timestamp.now()
        w_last = weekly_full.index[-1]
        m_last = monthly_full.index[-1]
        w_incomplete = (w_last.isocalendar().week == today.isocalendar().week and w_last.isocalendar().year == today.isocalendar().year)
        m_incomplete = (m_last.month == today.month and m_last.year == today.year)

        def _describe_intra_bar(bar_days_df, prev_high, prev_low):
            """提取未完成K线内的关键事实。

            返回 (cum_pct, desc, broke_range)
            broke_range: 是否突破前一根K线的区间
            """
            if len(bar_days_df) == 0:
                return 0.0, "", False
            cum = (bar_days_df["close"].iloc[-1] - bar_days_df["open"].iloc[0]) / bar_days_df["open"].iloc[0] * 100
            bar_vol = bar_days_df["volume"].mean()
            first_idx = bar_days_df.index[0]
            hist_mask = full_df.index < first_idx
            hist_vol = full_df.loc[hist_mask, "volume"].tail(20).mean() if hist_mask.any() else bar_vol
            vol_r = bar_vol / hist_vol if hist_vol > 0 else 1.0
            last_c = bar_days_df["close"].iloc[-1]
            broke_up = last_c > prev_high
            broke_down = last_c < prev_low

            desc_parts = [f"{cum:+.1f}%"]
            if vol_r > 2.0:
                desc_parts.append(f"量{vol_r:.0f}倍")
            elif vol_r > 1.3:
                desc_parts.append("放量")
            if broke_up:
                desc_parts.append(f"突破前高{prev_high:.2f}")
            elif broke_down:
                desc_parts.append(f"跌破前低{prev_low:.2f}")

            # 均线结构（纯上下文标注，不做评分）
            bar_dir = 1 if cum > 0 else -1
            close_now = bar_days_df["close"].iloc[-1]
            ema5_now = bar_days_df["ema5"].iloc[-1]
            ema39_now = bar_days_df["ema39"].iloc[-1]
            above_ema5 = close_now > ema5_now
            above_ema39 = close_now > ema39_now

            first_date = bar_days_df.index[0]
            before = full_df.index < first_date
            crossed_ema = False
            if before.any():
                prev = full_df[before].iloc[-1]
                crossed_ema = ((prev["close"] <= prev["ema5"] and close_now > ema5_now) or
                               (prev["close"] >= prev["ema5"] and close_now < ema5_now) or
                               (prev["close"] <= prev["ema39"] and close_now > ema39_now) or
                               (prev["close"] >= prev["ema39"] and close_now < ema39_now))

            if bar_dir > 0 and above_ema5 and above_ema39:
                desc_parts.append("刚站上EMA5/EMA39" if crossed_ema else "站上EMA5/EMA39")
            elif bar_dir < 0 and not above_ema5 and not above_ema39:
                desc_parts.append("刚跌破EMA5/EMA39" if crossed_ema else "跌破EMA5/EMA39")
            elif bar_dir > 0 and above_ema5:
                desc_parts.append("站上EMA5（EMA39下方）")
            elif bar_dir < 0 and not above_ema5:
                desc_parts.append("跌破EMA5（EMA39上方）")
            elif bar_dir < 0 and above_ema5:
                desc_parts.append("仍站上EMA5/EMA39" if above_ema39 else "仍站上EMA5")
            elif bar_dir > 0 and not above_ema5:
                desc_parts.append("仍低于EMA5/EMA39" if not above_ema39 else "仍低于EMA5")

            return cum, "，".join(desc_parts), broke_up or broke_down

        # 计算完成度并提取日内事实
        import calendar
        w_days_done = w_elapsed = 0
        m_days_done = m_elapsed = 0
        w_detail = m_detail = ""
        w_broke = m_broke = False

        if w_incomplete:
            iso = full_df.index.isocalendar()
            w_mask = (iso.year == today.isocalendar().year) & (iso.week == today.isocalendar().week)
            w_bar_days = full_df[w_mask]
            w_days_done = len(w_bar_days)
            w_elapsed = min(today.weekday() + 1, 5)
            prev_w = weekly_full.iloc[-2] if len(weekly_full) >= 2 else None
            w_cum, w_detail, w_broke = _describe_intra_bar(
                w_bar_days,
                prev_w["high"] if prev_w is not None else 99999,
                prev_w["low"] if prev_w is not None else 0,
            )

        if m_incomplete:
            m_mask = (full_df.index.year == today.year) & (full_df.index.month == today.month)
            m_bar_days = full_df[m_mask]
            m_days_done = len(m_bar_days)
            m_elapsed = today.day
            prev_m = monthly_full.iloc[-2] if len(monthly_full) >= 2 else None
            m_cum, m_detail, m_broke = _describe_intra_bar(
                m_bar_days,
                prev_m["high"] if prev_m is not None else 99999,
                prev_m["low"] if prev_m is not None else 0,
            )

        # ── 输出未完成K线实况 ──
        if w_incomplete:
            w_pct = w_elapsed * 20
            lines.append(f"- **本周实况**（{w_days_done}/{5}天，{w_pct}%）：{w_detail}")
        if m_incomplete:
            m_total = calendar.monthrange(today.year, today.month)[1]
            m_pct = m_elapsed * 100 // m_total
            lines.append(f"- **本月实况**（约{m_elapsed}/{m_total}天，{m_pct}%）：{m_detail}")

        # ── 可信度：完成度为主，突破信号可提升一级 ──
        def _confidence(complete_pct, broke_range=False):
            base = "高" if complete_pct >= 80 else ("中" if complete_pct >= 40 else "低")
            if broke_range and base == "低":
                return "中"  # 突破前K区间：即使完成度低也值得关注
            return base

        w_conf = _confidence(w_elapsed * 20, w_broke) if w_incomplete else "高"
        m_pct_val = m_elapsed * 100 // calendar.monthrange(today.year, today.month)[1] if m_incomplete else 100
        m_conf = _confidence(m_pct_val, m_broke) if m_incomplete else "高"

        def _conf_label(conf):
            return {"高": "可信", "中": "参考", "低": "不足"}[conf]

        w_tag = f"（可信度{_conf_label(w_conf)}）" if w_incomplete else ""
        m_tag = f"（可信度{_conf_label(m_conf)}）" if m_incomplete else ""
        lines.append(f"- **周线评估**：{w_dir}{w_tag}")
        lines.append(f"- **月线评估**：{m_dir}{m_tag}")

        if w_incomplete and w_conf == "低":
            lines.append(f"  → 本周仅{w_days_done}天，数据不足以判断周线方向，需周三后重新评估")
        elif w_incomplete and w_conf == "中" and w_broke:
            lines.append(f"  → 本周已突破前周区间，信号值得关注但交易日少")
        if m_incomplete and m_conf == "低":
            lines.append(f"  → 本月交易日过少，月线方向暂不可判断")

        # ── 综合结论（使用有效方向）──
        w_dir_eff = w_dir if (not w_incomplete or w_conf != "低") else "不足"
        m_dir_eff = m_dir if (not m_incomplete or m_conf != "低") else "不足"
        w_r, m_r = _dir_rank(w_dir_eff), _dir_rank(m_dir_eff)

        if w_r == 99 and m_r == 99:
            lines.append(f"- **结论**：周线和月线均无法判断 → 中期方向不明，日线信号降权处理")
        elif w_r == 99:
            lines.append(f"- **结论**：周线无法判断，月线{m_dir_eff}有参考价值 → 中线{m_dir_eff}但需周线确认")
        elif m_r == 99:
            lines.append(f"- **结论**：月线无法判断，周线{w_dir_eff}有参考价值 → 仅短线{w_dir_eff}参考")
        elif w_r > 0 and m_r > 0:
            caveat = "（待收盘确认）" if (w_incomplete or m_incomplete) else ""
            lines.append(f"- **结论**：周线月线共振偏多 → 中期趋势向上，日线做多信号可信度较高{caveat}")
        elif w_r < 0 and m_r < 0:
            caveat = "（待收盘确认）" if (w_incomplete or m_incomplete) else ""
            lines.append(f"- **结论**：周线月线共振偏空 → 中期趋势向下，日线做多信号需格外谨慎{caveat}")
        elif w_dir_eff == "震荡" and m_dir_eff == "震荡":
            lines.append(f"- **结论**：周线月线均处于震荡 → 中期方向不明，日线信号权重降低")
        elif w_dir_eff == "止跌" and m_r < 0:
            lines.append(f"- **结论**：周线出现止跌信号但月线仍在弱势 → 短线可能反弹，但中期趋势未扭转，做多仅限短线")
        elif w_dir_eff == "转弱" and m_r > 0:
            lines.append(f"- **结论**：周线转弱但月线仍偏多 → 短线回调，中期趋势未破坏，关注支撑位")
        else:
            lines.append(f"- **结论**：周线({w_dir_eff})与月线({m_dir_eff})方向不一致 → 周期矛盾，日线信号降权处理")

    # ── 大周期定调回填到报告顶部 ──
    if w_r == 99 and m_r == 99:
        _top = "### 大周期定调\n\n周线和月线均完成度过低，不做大周期方向预判，待更多交易日数据后重新评估\n"
    elif w_r == 99:
        _top = f"### 大周期定调\n\n周线无法判断（完成度{_conf_label(w_conf)}），月线{m_dir_eff}（可信度{m_conf}）→ 中线{m_dir_eff}概率较高但周线确认不足\n"
    elif m_r == 99:
        _top = f"### 大周期定调\n\n月线无法判断（完成度{_conf_label(m_conf)}），周线{w_dir_eff}（可信度{w_conf}）→ 仅短线{w_dir_eff}参考\n"
    else:
        has_partial = w_incomplete or m_incomplete
        _pfx = "（待收盘确认）" if has_partial else ""
        if w_r > 0 and m_r > 0:
            _top = f"### 大周期定调\n\n周线{w_dir_eff} + 月线{m_dir_eff} → 共振偏多，日线做多信号可信度较高{_pfx}\n"
        elif w_r < 0 and m_r < 0:
            _top = f"### 大周期定调\n\n周线{w_dir_eff} + 月线{m_dir_eff} → 共振偏空，日线做多信号需格外谨慎{_pfx}\n"
        elif w_r >= 0 and m_r < 0:
            _top = f"### 大周期定调\n\n周线{w_dir_eff} + 月线{m_dir_eff} → 周期矛盾，短线反弹但中期未扭转\n"
        elif w_r < 0 and m_r >= 0:
            _top = f"### 大周期定调\n\n周线{w_dir_eff} + 月线{m_dir_eff} → 周期矛盾，短线回调但中期趋势未破坏\n"
        else:
            _top = f"### 大周期定调\n\n周线{w_dir_eff} + 月线{m_dir_eff} → 周期矛盾，日线信号降权处理\n"
    lines[_mtf_slot] = _top

    return "\n".join(lines)


def make_cache_key(ticker: str, trade_date: str) -> str:
    return f"{ticker}_{trade_date}"


def _safe(tool, payload: dict) -> Any:
    start_t = time.time()
    try:
        res = tool.invoke(payload)
        duration = time.time() - start_t
        # 仅在耗时较长时输出
        if duration > 0.5:
            print(f"  [Timer] {getattr(tool, 'name', str(tool))} took {duration:.2f}s")
        return res
    except Exception as exc:
        return f"{getattr(tool, 'name', str(tool))} 调用失败：{type(exc).__name__}: {exc}"


def _fetch_all(ticker: str, trade_date: str) -> Dict[str, Any]:
    """Fetch all data sources in parallel.

    Always fetches full data including financial statements, regardless of horizon.
    The horizon only affects the analysis window, not data collection.
    """
    lookback = LONG_DAYS
    end_dt = datetime.strptime(trade_date, "%Y-%m-%d")
    # 为了计算指标准确（如 200 SMA），需要比分析窗口更长的历史数据
    fetch_lookback = 365
    start_str = (end_dt - timedelta(days=fetch_lookback)).strftime("%Y-%m-%d")

    tasks: Dict[str, tuple] = {
        "stock_data": (get_stock_data, {"symbol": ticker, "start_date": start_str, "end_date": trade_date}),
        "news": (get_news, {"ticker": ticker, "start_date": (end_dt - timedelta(days=lookback)).strftime("%Y-%m-%d"), "end_date": trade_date}),
        "global_news": (get_global_news, {"curr_date": trade_date, "look_back_days": lookback, "limit": 30}),
        "fund_flow_board": (get_board_fund_flow, {}),
        "fund_flow_individual": (get_individual_fund_flow, {"symbol": ticker}),
        "lhb": (get_lhb_detail, {"symbol": ticker, "date": trade_date}),
        "insider_transactions": (get_insider_transactions, {"ticker": ticker}),
        "zt_pool": (get_zt_pool, {"date": trade_date}),
        "hot_stocks": (get_hot_stocks_xq, {}),
    }

    # 财务报表类数据始终拉取，Research Manager 根据 horizon 自行判断权重
    tasks.update({
        "fundamentals": (get_fundamentals, {"ticker": ticker, "curr_date": trade_date}),
        "balance_sheet": (get_balance_sheet, {"ticker": ticker, "freq": "quarterly", "curr_date": trade_date}),
        "cashflow": (get_cashflow, {"ticker": ticker, "freq": "quarterly", "curr_date": trade_date}),
        "income_statement": (get_income_statement, {"ticker": ticker, "freq": "quarterly", "curr_date": trade_date}),
    })

    # 新增数据源：北向资金、融资融券、大宗交易、龙虎榜席位、机构调研、股东增减持、限售解禁、股权质押
    week_ago = (end_dt - timedelta(days=7)).strftime("%Y-%m-%d")
    tasks.update({
        "hsgt_individual": (get_hsgt_individual, {"symbol": ticker}),
        "hsgt_flow": (get_hsgt_flow, {}),
        "margin_detail": (get_margin_detail, {"symbol": ticker, "date": trade_date}),
        "block_trades": (get_block_trades, {"symbol": ticker, "start_date": week_ago, "end_date": trade_date}),
        "lhb_institution_stats": (get_lhb_institution_stats, {"symbol": ticker, "start_date": week_ago, "end_date": trade_date}),
        "lhb_active_seats": (get_lhb_active_seats, {"start_date": week_ago, "end_date": trade_date}),
        "research_reports": (get_research_reports, {"symbol": ticker}),
        "shareholder_changes": (get_shareholder_changes, {"symbol": ticker}),
        "restricted_release": (get_restricted_release, {"symbol": ticker}),
        "pledge_ratio": (get_pledge_ratio, {"date": trade_date}),
    })

    # Phase 2: 资金面/筹码/板块
    tasks.update({
        "shareholder_count": (get_shareholder_count, {"symbol": ticker}),
        "dividend_history": (get_dividend_history, {"symbol": ticker}),
        "concept_board": (get_concept_board, {"symbol": ticker}),
        "fund_flow_120d": (get_individual_fund_flow_120d, {"symbol": ticker}),
    })

    # Phase 3: mootdx 盘口/F10/逐笔 + 巨潮公告
    level2_date = end_dt.strftime("%Y%m%d")
    tasks.update({
        "orderbook": (get_five_level_orderbook, {"symbol": ticker}),
        "f10_detail": (get_f10_detail, {"symbol": ticker, "category": 0}),
        "level2_quotes": (get_level2_quotes, {"symbol": ticker, "date": level2_date}),
        "cninfo_announcements": (get_cninfo_announcements, {"symbol": ticker, "start_date": week_ago, "end_date": trade_date}),
    })

    results: Dict[str, Any] = {}
    fetch_start = time.time()
    # 减少并发池大小，避免被反爬
    with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as executor:
        future_to_key = {executor.submit(_safe, tool, payload): key for key, (tool, payload) in tasks.items()}
        for future in future_to_key:
            key = future_to_key[future]
            result = future.result()
            # 过滤错误字符串，避免伪装成数据传给 LLM
            if isinstance(result, str) and "调用失败" in result:
                print(f"  [Warning] {key}: {result}")
                results[key] = None
            else:
                results[key] = result

    # ── Parse CSV once, reuse for indicators and VPA ──────────────────
    raw_csv = results.get("stock_data", "")
    df = _parse_csv_to_dataframe(raw_csv)

    # ── 核心加速：本地计算所有技术指标 ──────────────────
    indicators_res = {}
    try:
        if df is not None and "close" in df.columns:
            ss = wrap(df.copy())

            calc_map = {
                "close_50_sma": "close_50_sma",
                "close_200_sma": "close_200_sma",
                "close_10_ema": "close_10_ema",
                "rsi": "rsi_14",
                "macd": "macd",
                "boll": "close_20_sma",
                "boll_ub": "boll_ub",
                "boll_lb": "boll_lb",
                "atr": "atr",
                "vwma": "vwma"
            }

            for key, ss_key in calc_map.items():
                try:
                    val = ss[ss_key].iloc[-1]
                    indicators_res[key] = round(float(val), 2) if isinstance(val, (int, float)) else str(val)
                except Exception:
                    indicators_res[key] = "N/A"
        else:
            print(f"  [Warning] No valid stock_data for indicator calculation.")
    except Exception as e:
        print(f"  [Error] Local indicator calculation failed: {e}")

    for ind in INDICATORS:
        if ind not in indicators_res:
            indicators_res[ind] = "无数据"

    results["indicators"] = indicators_res

    # ── VPA 预计算指标 ──────────────────────────────
    try:
        if df is not None:
            results["vpa_indicators"] = _compute_vpa_indicators(df.copy())
        else:
            results["vpa_indicators"] = "VPA 数据不足"
    except Exception as e:
        results["vpa_indicators"] = f"VPA 计算失败：{e}"

    # ── 概念共振分析（仅增强模式）──────────────────
    if os.getenv("TA_ENHANCED", "1") not in ("0", "false", "no"):
        try:
            from tradingagents.dataflows.concept_resonance import (
                compute_concept_resonance,
                format_resonance_for_prompt,
                extract_returns_from_df,
            )
            stock_returns = extract_returns_from_df(df) if df is not None else None
            resonance_result = compute_concept_resonance(ticker, trade_date, stock_returns=stock_returns)
            results["concept_resonance"] = resonance_result
            results["concept_resonance_text"] = format_resonance_for_prompt(resonance_result)
        except Exception as e:
            results["concept_resonance"] = None
            results["concept_resonance_text"] = f"概念共振计算失败：{e}"
    else:
        results["concept_resonance"] = None
        results["concept_resonance_text"] = ""

    print(f"[Timer] Total Data Collection for {ticker} took {time.time() - fetch_start:.2f}s")
    return results


class DataCollector:
    """Collect and cache data, thread-safe and shareable across jobs."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()
        self._refcounts: Dict[str, int] = {}

    def _get_key_lock(self, key: str) -> threading.Lock:
        with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def collect(self, ticker: str, trade_date: str, horizons: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fetch all data and store in cache.

        Thread-safe: concurrent calls for the same ticker+date will block
        on a per-key lock, so data is fetched only once.
        """
        key = make_cache_key(ticker, trade_date)
        key_lock = self._get_key_lock(key)
        with key_lock:
            if key not in self._cache:
                self._cache[key] = _fetch_all(ticker, trade_date)
        return self._cache[key]

    def get(self, ticker: str, trade_date: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached pool, or None if not collected yet."""
        return self._cache.get(make_cache_key(ticker, trade_date))

    def get_window(
        self,
        pool: Dict[str, Any],
        horizon: str,
        trade_date: str,
    ) -> Dict[str, Any]:
        """Return pool copy annotated with horizon window metadata."""
        days = SHORT_DAYS if horizon == "short" else LONG_DAYS
        result = dict(pool)
        result["_data_window"] = f"{days}天"
        result["_horizon"] = horizon
        return result

    def ref(self, ticker: str, trade_date: str) -> None:
        """Increment reference count (call before using cached data)."""
        key = make_cache_key(ticker, trade_date)
        with self._meta_lock:
            self._refcounts[key] = self._refcounts.get(key, 0) + 1

    def evict(self, ticker: str, trade_date: str) -> None:
        """Decrement refcount and remove cached data when no one needs it."""
        key = make_cache_key(ticker, trade_date)
        with self._meta_lock:
            count = self._refcounts.get(key, 1) - 1
            if count <= 0:
                self._cache.pop(key, None)
                self._refcounts.pop(key, None)
                # 不删除 _locks[key]：其他线程可能仍持有该锁的引用，
                # 删除会导致新 collect() 创建新锁，破坏互斥。
                # 锁对象很轻量，留着不影响内存。
            else:
                self._refcounts[key] = count
