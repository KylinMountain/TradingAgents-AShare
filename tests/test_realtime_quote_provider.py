"""Tests for realtime quote provider integration."""
import json
import pytest
from unittest.mock import patch
import pandas as pd


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
    with patch.object(provider, "_ak") as mock_ak:
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


def test_route_to_vendor_resolves_realtime_quotes():
    """route_to_vendor can route get_realtime_quotes to the correct category."""
    from tradingagents.dataflows.interface import get_category_for_method
    category = get_category_for_method("get_realtime_quotes")
    assert category == "realtime_data"
