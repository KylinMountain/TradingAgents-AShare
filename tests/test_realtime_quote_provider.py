"""Tests for realtime quote provider integration."""
import json
import pytest
from unittest.mock import patch
import pandas as pd
from dotenv import load_dotenv
load_dotenv()


def test_akshare_get_realtime_quotes_returns_structured_json():
    """CnAkshareProvider.get_realtime_quotes returns JSON with expected fields."""
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider

    mock_df = pd.DataFrame({
        "代码": ["600519", "000001"],
        "名称": ["贵州茅台", "平安银行"],
        "最新价": [1800.0, 12.5],
        "今开": [1790.0, 12.3],
        "最高": [1810.0, 12.6],
        "最低": [1785.0, 12.2],
        "昨收": [1795.0, 12.4],
        "成交量": [50000, 800000],
        "成交额": [90000000, 10000000],
    })

    provider = CnAkshareProvider()
    # Mock Sina to fail so it falls back to Eastmoney mock
    with patch.object(provider, "_fetch_quotes_sina", return_value="{}"), \
         patch.object(provider, "_ak") as mock_ak:
        mock_ak.return_value.stock_zh_a_spot_em.return_value = mock_df
        result = provider.get_realtime_quotes(["600519.SH", "000001.SZ"])

    data = json.loads(result)
    assert "600519.SH" in data
    q = data["600519.SH"]
    assert q["price"] == 1800.0
    assert q["previous_close"] == 1795.0
    assert q["change"] == 5.0
    assert q["change_pct"] == pytest.approx(0.2786, abs=0.001)
    assert q["open"] == 1790.0
    assert q["volume"] == 50000
    assert "000001.SZ" in data


def test_akshare_get_realtime_quotes_empty_symbols():
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider

    provider = CnAkshareProvider()
    result = provider.get_realtime_quotes([])
    assert json.loads(result) == {}


def test_get_stock_data_includes_today():
    """get_stock_data 返回结果应包含今日数据（_maybe_append_realtime_row 补充）。"""
    import datetime
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider

    provider = CnAkshareProvider()
    today = datetime.date.today().strftime("%Y-%m-%d")
    start = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    result = provider.get_stock_data("300432.SZ", start, today)
    assert today in result, f"今日 {today} 未出现在返回数据中:\n{result}"


def test_maybe_append_realtime_row():
    """逐步测试 _maybe_append_realtime_row 的每个判断条件"""
    import datetime
    import pandas as pd
    from tradingagents.dataflows.providers.cn_akshare_provider import CnAkshareProvider
    from tradingagents.dataflows.trade_calendar import cn_market_phase, cn_today_str, is_cn_trading_day

    provider = CnAkshareProvider()
    today_str = cn_today_str()
    today = pd.to_datetime(today_str)

    print(f"\n今天: {today_str}")
    print(f"是否交易日: {is_cn_trading_day(today_str)}")
    print(f"市场阶段: {cn_market_phase()}")

    # 构造不含今日的历史数据
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    hist_df = pd.DataFrame([{
        "Date": pd.to_datetime(yesterday),
        "Open": 11.0, "High": 11.2, "Low": 10.9, "Close": 11.1, "Volume": 100000.0,
    }])

    print(f"\n历史数据日期: {hist_df['Date'].tolist()}")

    # 测试实时行
    print("\n--- 测试 _fetch_realtime_row ---")
    try:
        rt = provider._fetch_realtime_row("002064")
        print(f"返回行数: {len(rt)}")
        if not rt.empty:
            print(f"Date: {rt.iloc[0]['Date']}")
            print(f"Close: {rt.iloc[0]['Close']}")
            date_match = pd.to_datetime(rt.iloc[0]["Date"]).normalize() == today
            print(f"日期匹配今天: {date_match}")
        else:
            print("返回空 DataFrame")
    except Exception as e:
        print(f"_fetch_realtime_row 异常: {type(e).__name__}: {e}")

    # 测试完整方法
    print("\n--- 测试 _maybe_append_realtime_row ---")
    result = provider._maybe_append_realtime_row("002064", hist_df.copy(), today_str)
    print(f"结果行数: {len(result)}")
    print(f"日期列表: {result['Date'].tolist()}")
    has_today = (pd.to_datetime(result["Date"]).dt.normalize() == today).any()
    print(f"包含今日数据: {has_today}")
    if has_today:
        today_row = result[pd.to_datetime(result["Date"]).dt.normalize() == today]
        print(f"\n今日数据明细:\n{today_row.to_string(index=False)}")


def test_route_to_vendor_resolves_realtime_quotes():
    """route_to_vendor can route get_realtime_quotes to the correct category."""
    from tradingagents.dataflows.interface import get_category_for_method
    category = get_category_for_method("get_realtime_quotes")
    assert category == "realtime_data"
