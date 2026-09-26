import pandas as pd
import pytest

from scheduler.intraday_rules import (
    BoardAnomaly,
    detect_board_anomalies,
    detect_zt_pool_concentration,
)


def _row(name, change_pct, net_inflow):
    return {"行业": name, "行业-涨跌幅": change_pct, "净额": net_inflow}


def test_empty_dataframe_returns_no_anomalies():
    assert detect_board_anomalies(pd.DataFrame()) == []
    assert detect_board_anomalies(None) == []


def test_missing_columns_returns_no_anomalies():
    df = pd.DataFrame([{"行业": "x", "foo": 1}])
    assert detect_board_anomalies(df) == []


@pytest.mark.parametrize(
    "change_pct,net_inflow,expected_case",
    [
        (1.1, 3.1, "A"),      # 量价确认
        (2.1, -1.1, "B"),     # 量价背离
        (0.9, 5.1, "C"),      # 暗中吸筹
        (-1.6, -3.1, "D"),    # 真下杀
        (-2.1, 2.1, "E"),     # 逆势吸筹
    ],
)
def test_each_case_triggers_correctly(change_pct, net_inflow, expected_case):
    df = pd.DataFrame([_row("测试板块", change_pct, net_inflow)])
    result = detect_board_anomalies(df)
    assert result == [BoardAnomaly("测试板块", expected_case, change_pct, net_inflow)]


@pytest.mark.parametrize(
    "change_pct,net_inflow",
    [
        (1.0, 3.0),    # 正好在 Case A 的边界上（不含等于），不应触发
        (0.5, 0.5),    # 完全平淡的一天
        (2.5, 0.0),    # 涨但资金持平，不构成量价确认也不构成背离
    ],
)
def test_boundary_and_flat_values_do_not_trigger(change_pct, net_inflow):
    df = pd.DataFrame([_row("平淡板块", change_pct, net_inflow)])
    assert detect_board_anomalies(df) == []


def test_multiple_rows_only_returns_matching_ones():
    df = pd.DataFrame(
        [
            _row("异动板块", 1.5, 4.0),   # Case A
            _row("平淡板块", 0.2, 0.5),   # 无异动
        ]
    )
    result = detect_board_anomalies(df)
    assert len(result) == 1
    assert result[0].board_name == "异动板块"
    assert result[0].anomaly_case == "A"


def test_nan_rows_are_skipped():
    df = pd.DataFrame([{"行业": "缺数据板块", "行业-涨跌幅": None, "净额": 5.0}])
    assert detect_board_anomalies(df) == []


def test_nan_board_name_is_skipped():
    df = pd.DataFrame([{"行业": float("nan"), "行业-涨跌幅": 1.5, "净额": 4.0}])
    assert detect_board_anomalies(df) == []


def test_case_e_not_masked_by_case_c_when_net_inflow_is_large():
    # Regression: a falling board with net_inflow > 5 used to be misclassified
    # as C ("quiet accumulation", shown in a bullish tone) instead of E
    # ("accumulation against the drop", a mixed/warning signal).
    df = pd.DataFrame([_row("重挫板块", -3.0, 6.0)])
    result = detect_board_anomalies(df)
    assert result == [BoardAnomaly("重挫板块", "E", -3.0, 6.0)]


def test_zt_pool_concentration_threshold():
    below = pd.DataFrame([{"code": i} for i in range(80)])
    above = pd.DataFrame([{"code": i} for i in range(81)])
    assert detect_zt_pool_concentration(below) is False
    assert detect_zt_pool_concentration(above) is True
    assert detect_zt_pool_concentration(pd.DataFrame()) is False
    assert detect_zt_pool_concentration(None) is False
