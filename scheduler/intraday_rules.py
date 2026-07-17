"""Rule-based (no-LLM) intraday anomaly detection for concept boards.

Pure functions only, so the thresholds and edge cases can be unit tested
without touching akshare or any network call. See
docs/superpowers/specs/2026-07-10-intraday-analysis-design.md for the
Case A-E rationale (ported from AlphaAgents' intraday_monitor.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Concept board column names as returned by CnAkshareProvider.get_concept_fund_flow_df().
_COL_BOARD_NAME = "行业"  # akshare's own naming; this is actually the concept board name
_COL_CHANGE_PCT = "行业-涨跌幅"
_COL_NET_INFLOW = "净额"  # unit: 亿元 (100M yuan)

# 涨停家数集中度阈值:普通交易日涨停 30-90 家,30 的阈值会让 boost 几乎全天
# 挂在 2 分钟轮询档而失去意义;80 以上才视为市场级异动。
_ZT_POOL_ANOMALY_THRESHOLD = 80


@dataclass(frozen=True)
class BoardAnomaly:
    board_name: str
    anomaly_case: str
    change_pct: float
    net_inflow: float


def detect_board_anomalies(concept_fund_flow_df: pd.DataFrame) -> list[BoardAnomaly]:
    """Detect concept-board anomalies from a fund-flow ranking snapshot.

    Case A: change > 1.0% and net_inflow > 3 (亿)   -- confirmed anomaly (price+flow agree)
    Case B: change > 2.0% and net_inflow < -1 (亿)  -- divergence, possible distribution
    Case C: change < 1.0% and net_inflow > 5 (亿)   -- quiet accumulation
    Case D: change < -1.5% and net_inflow < -3 (亿) -- real sell-off
    Case E: change < -2.0% and net_inflow > 2 (亿)  -- accumulation against the drop

    Returns one BoardAnomaly per board that matches, empty list if none/empty input.
    """
    if concept_fund_flow_df is None or concept_fund_flow_df.empty:
        return []
    if _COL_CHANGE_PCT not in concept_fund_flow_df.columns or _COL_NET_INFLOW not in concept_fund_flow_df.columns:
        return []

    anomalies: list[BoardAnomaly] = []
    for _, row in concept_fund_flow_df.iterrows():
        change_pct = row.get(_COL_CHANGE_PCT)
        net_inflow = row.get(_COL_NET_INFLOW)
        board_name = row.get(_COL_BOARD_NAME)
        if pd.isna(change_pct) or pd.isna(net_inflow) or pd.isna(board_name) or not str(board_name).strip():
            continue
        change_pct = float(change_pct)
        net_inflow = float(net_inflow)

        case = _classify(change_pct, net_inflow)
        if case:
            anomalies.append(
                BoardAnomaly(
                    board_name=str(board_name),
                    anomaly_case=case,
                    change_pct=change_pct,
                    net_inflow=net_inflow,
                )
            )
    return anomalies


def _classify(change_pct: float, net_inflow: float) -> str | None:
    # D and E must be checked before C: C's range (change_pct < 1.0, i.e. "not
    # really rising") is broad enough to also match any drop, so a falling
    # board with net_inflow > 5 would otherwise be misclassified as the
    # benign "quiet accumulation" C instead of D/E.
    if change_pct > 1.0 and net_inflow > 3:
        return "A"
    if change_pct > 2.0 and net_inflow < -1:
        return "B"
    if change_pct < -1.5 and net_inflow < -3:
        return "D"
    if change_pct < -2.0 and net_inflow > 2:
        return "E"
    if change_pct < 1.0 and net_inflow > 5:
        return "C"
    return None


def detect_zt_pool_concentration(zt_pool_df: pd.DataFrame) -> bool:
    """涨停家数集中度信号：涨停家数超过阈值视为市场级异动信号。"""
    if zt_pool_df is None or zt_pool_df.empty:
        return False
    return len(zt_pool_df) > _ZT_POOL_ANOMALY_THRESHOLD
