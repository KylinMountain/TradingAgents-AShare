"""Tests for 今日投资 (Investoday) realtime quote provider."""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


def test_investoday_get_realtime_quotes_maps_fields():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    api_body = {
        "code": 0,
        "message": "success",
        "data": {
            "stockCode": "002594",
            "stockName": "比亚迪",
            "marketType": "sz",
            "openPrice": 359.89,
            "closePriceYDay": 361.99,
            "currentPrice": 353.86,
            "changeRatio": -0.02245918,
            "highPrice": 359.89,
            "lowPrice": 353.62,
            "dataTime": "2025-06-12 13:40:21",
            "dealStockAmount": 100071,
            "dealMoney": 3563408640,
        },
    }

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = api_body

    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="test-key"), \
         patch("tradingagents.dataflows.providers.cn_investoday_provider.requests.get", return_value=mock_resp) as mock_get:
        out = provider.get_realtime_quotes(["002594.SZ"])

    mock_get.assert_called_once()
    call_kw = mock_get.call_args[1]
    assert call_kw["params"] == {"stockCode": "002594"}
    assert call_kw["headers"] == {"apiKey": "test-key"}

    data = json.loads(out)
    assert "002594.SZ" in data
    q = data["002594.SZ"]
    assert q["price"] == 353.86
    assert q["previous_close"] == 361.99
    assert q["change"] == pytest.approx(-8.13, rel=1e-4)
    assert q["change_pct"] == pytest.approx(-2.2459, rel=1e-3)
    assert q["open"] == 359.89
    assert q["high"] == 359.89
    assert q["low"] == 353.62
    assert q["volume"] == 100071.0
    assert q["amount"] == 3563408640.0
    assert q["quote_time"] == "2025-06-12 13:40:21"
    assert q["source"] == "investoday"


def test_investoday_get_realtime_quotes_no_api_key():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value=""):
        with pytest.raises(NotImplementedError, match="API Key"):
            provider.get_realtime_quotes(["600519.SH"])


def test_investoday_get_realtime_quotes_empty_and_invalid_symbols():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"):
        assert json.loads(provider.get_realtime_quotes([])) == {}
        assert json.loads(provider.get_realtime_quotes(["", "  ", "INVALID"])) == {}


def test_investoday_get_realtime_quotes_all_failed_raises():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"code": 1, "message": "error", "data": None}

    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"), \
         patch("tradingagents.dataflows.providers.cn_investoday_provider.requests.get", return_value=mock_resp):
        with pytest.raises(NotImplementedError, match="未获取到任何实时行情"):
            provider.get_realtime_quotes(["600519.SH"])


def test_build_default_registry_includes_cn_investoday():
    from tradingagents.dataflows.providers.registry import build_default_registry

    reg = build_default_registry()
    assert "cn_investoday" in reg.list_names()
    assert reg.get("cn_investoday") is not None


def _mock_json_response(body: dict):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = body
    return mock_resp


def test_investoday_get_news_success():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    body = {
        "code": 0,
        "message": "success",
        "data": [
            {
                "date": "2025-04-02 15:45:02",
                "newsId": "NEWS001",
                "title": "测试标题",
                "summary": "摘要内容" * 30,
                "keyPoints": "要点A",
                "impactAnalysis": "影响简述",
            }
        ],
    }
    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"), \
         patch(
             "tradingagents.dataflows.providers.cn_investoday_provider.requests.get",
             return_value=_mock_json_response(body),
         ) as mock_get:
        out = provider.get_news("600519.SH", "2025-04-01", "2025-04-03")

    assert "## 600519.SH 新闻" in out
    assert "测试标题" in out
    assert "source: 今日投资" in out
    assert "newsId: NEWS001" in out
    call_kw = mock_get.call_args[1]
    assert call_kw["params"]["stockCode"] == "600519"
    assert call_kw["params"]["beginTime"] == "2025-04-01 00:00:00"
    assert call_kw["params"]["endTime"] == "2025-04-03 23:59:59"


def test_investoday_get_news_no_api_key():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value=""):
        with pytest.raises(NotImplementedError, match="API Key"):
            provider.get_news("600519.SH", "2025-04-01", "2025-04-02")


def test_investoday_get_news_invalid_ticker():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"):
        out = provider.get_news("INVALID", "2025-04-01", "2025-04-02")
    assert "无法解析证券代码" in out


def test_investoday_get_news_empty_returns_message():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    body = {"code": 0, "message": "success", "data": []}
    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"), \
         patch(
             "tradingagents.dataflows.providers.cn_investoday_provider.requests.get",
             return_value=_mock_json_response(body),
         ):
        out = provider.get_news("600519.SH", "2025-04-01", "2025-04-02")
    assert "No news found" in out


def test_investoday_get_global_news_uses_macro_then_broad_fallback():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    empty_macro = {"code": 0, "message": "success", "data": []}
    broad = {
        "code": 0,
        "message": "success",
        "data": [{"date": "2025-04-01 10:00:00", "title": "宏观条目", "summary": "正文"}],
    }
    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"), \
         patch(
             "tradingagents.dataflows.providers.cn_investoday_provider.requests.get",
             side_effect=[_mock_json_response(empty_macro), _mock_json_response(broad)],
         ) as mock_get:
        out = provider.get_global_news("2025-04-02", look_back_days=2, limit=10)

    assert mock_get.call_count == 2
    assert "全球市场新闻" in out
    assert "宏观条目" in out
    assert mock_get.call_args_list[0][1]["params"].get("newsType") == 1
    assert "newsType" not in mock_get.call_args_list[1][1]["params"]


def test_investoday_get_global_news_no_api_key():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value=""):
        with pytest.raises(NotImplementedError, match="API Key"):
            provider.get_global_news("2025-04-02")


def test_investoday_get_global_news_request_fail_raises():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"), \
         patch(
             "tradingagents.dataflows.providers.cn_investoday_provider.requests.get",
             side_effect=OSError("network down"),
         ):
        with pytest.raises(NotImplementedError, match="cn_investoday"):
            provider.get_global_news("2025-04-02", look_back_days=1, limit=5)


def test_investoday_get_stock_data_csv_from_adjusted_quotes():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    rows = [
        {
            "date": "2025-01-02",
            "openPrice": 10.0,
            "highPrice": 11.0,
            "lowPrice": 9.5,
            "closePrice": 10.5,
            "volume": 10000.0,
        },
        {
            "date": "2025-01-03",
            "openPrice": 10.5,
            "highPrice": 12.0,
            "lowPrice": 10.4,
            "closePrice": 11.0,
            "volume": 12000.0,
        },
    ]
    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"), \
         patch.object(provider, "_fetch_paged_list", return_value=rows):
        out = provider.get_stock_data("600519.SH", "2025-01-02", "2025-01-03")

    assert "# Stock data for 600519.SH" in out
    assert "2025-01-02" in out
    assert "Open,High,Low,Close,Volume" in out or "Open" in out


def test_investoday_get_indicators_rsi_uses_stockstats():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    base = datetime(2024, 6, 1)
    rows = []
    for i in range(120):
        d = base + timedelta(days=i)
        p = 10.0 + i * 0.05
        rows.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "openPrice": p,
                "highPrice": p + 0.2,
                "lowPrice": p - 0.2,
                "closePrice": p + 0.1,
                "volume": 1e6 + i * 100,
            }
        )
    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"), \
         patch.object(provider, "_fetch_paged_list", return_value=rows):
        out = provider.get_indicators("000001.SZ", "rsi", "2024-09-28", look_back_days=14)

    assert "rsi" in out.lower()
    assert "2024-09-28" in out


def test_investoday_get_fundamentals_profiles():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    body = {
        "code": 0,
        "message": "success",
        "data": [{"stockCode": "600519", "stockName": "Moutai", "mainBusiness": "Beverage"}],
    }
    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"), \
         patch.object(provider, "_request_investoday", return_value=body):
        out = provider.get_fundamentals("600519.SH")

    assert "600519" in out or "Moutai" in out
    assert "Fundamentals" in out


def test_investoday_get_insider_exec_shrhld_markdown():
    from tradingagents.dataflows.providers.cn_investoday_provider import CnInvestodayProvider

    rows = [
        {
            "changeDate": "2024-01-02 00:00:00",
            "managerName": "ZhangSan",
            "sharesChange": 1000,
            "changeReason": "二级市场买卖",
        }
    ]
    provider = CnInvestodayProvider()
    with patch.object(provider, "_resolve_api_key", return_value="k"), \
         patch.object(provider, "_fetch_paged_list", return_value=rows):
        out = provider.get_insider_transactions("600519.SH")

    assert "高管持股变动" in out or "exec-shrhld-chg" in out
    assert "ZhangSan" in out
