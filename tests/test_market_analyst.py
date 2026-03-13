from unittest.mock import MagicMock
from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.graph.data_collector import DataCollector


def _make_state(horizon="short"):
    return {
        "trade_date": "2026-03-12",
        "company_of_interest": "600519",
        "horizon": horizon,
        "user_intent": {
            "raw_query": "test", "ticker": "600519",
            "horizons": ["short", "medium"], "focus_areas": [], "specific_questions": [],
        },
    }


def _stub_pool(horizon="short"):
    days = "14天" if horizon == "short" else "90天"
    return {
        "stock_data": "close,volume\n100,1000",
        "indicators": {k: "50" for k in [
            "close_50_sma","close_200_sma","close_10_ema",
            "rsi","macd","boll","boll_ub","boll_lb","atr","vwma"
        ]},
        "_data_window": days, "_horizon": horizon,
    }


def test_market_analyst_returns_trace():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content='报告\n<!-- VERDICT: {"direction": "看多", "reason": "趋势向上"} -->'
    )
    collector = DataCollector()
    collector._cache["600519_2026-03-12"] = _stub_pool("short")
    node = create_market_analyst(mock_llm, collector)
    result = node(_make_state("short"))
    assert "market_report" in result
    assert "analyst_traces" in result
    assert len(result["analyst_traces"]) == 1
    assert result["analyst_traces"][0]["agent"] == "market_analyst"
    assert result["analyst_traces"][0]["verdict"] == "看多"
    assert result["analyst_traces"][0]["horizon"] == "short"


def test_market_analyst_medium_window():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="report")
    collector = DataCollector()
    collector._cache["600519_2026-03-12"] = _stub_pool("medium")
    node = create_market_analyst(mock_llm, collector)
    result = node(_make_state("medium"))
    assert result["analyst_traces"][0]["data_window"] == "90天"
