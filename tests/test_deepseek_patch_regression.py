"""回归：本地补丁 2026-09-06（deepseek 端点优先级 + _log_state* UTF-8 写盘）。

不发起任何网络/LLM 调用，可离线执行。
"""

import json

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.factory import create_llm_client


def _llm_base(client) -> str:
    return client.get_llm().openai_api_base


def test_deepseek_ignores_openai_default_base_url(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    for bad in (
        "https://api.openai.com/v1",
        "https://api.openai.com/v1/",
        "https://api.openai.com",
    ):
        llm = _llm_base(
            create_llm_client(provider="deepseek", model="deepseek-chat", base_url=bad)
        )
        assert llm == "https://api.deepseek.com"


def test_deepseek_default_base_url_is_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    llm = _llm_base(create_llm_client(provider="deepseek", model="deepseek-chat"))
    assert llm == "https://api.deepseek.com"


def test_deepseek_honors_explicit_custom_gateway(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    llm = _llm_base(
        create_llm_client(
            provider="deepseek", model="deepseek-chat",
            base_url="https://gw.example.com/v1",
        )
    )
    assert llm == "https://gw.example.com/v1"


def test_graph_with_openai_default_backend_url_resolves_deepseek(monkeypatch):
    """复现 v3 触发条件：config.backend_url 仍是默认 api.openai.com/v1，
    provider=deepseek -> 两端 LLM 都必须解析到 DeepSeek 端点。"""
    from tradingagents.default_config import DEFAULT_CONFIG

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "deepseek"
    config["deep_think_llm"] = "deepseek-reasoner"
    config["quick_think_llm"] = "deepseek-chat"
    config["backend_url"] = "https://api.openai.com/v1"  # fork 默认值（含 bug 场景）
    config["api_key"] = ""
    ta = TradingAgentsGraph(debug=False, config=config)
    assert ta.deep_thinking_llm.openai_api_base == "https://api.deepseek.com"
    assert ta.quick_thinking_llm.openai_api_base == "https://api.deepseek.com"


def _nested_state_skeleton() -> dict:
    """覆盖 _log_state 读取的全部键。"""
    debate = {
        "bull_history": [], "bear_history": [], "history": [],
        "current_speaker": "", "current_response": "", "judge_decision": "",
        "claims": [], "focus_claim_ids": [], "open_claim_ids": [],
        "resolved_claim_ids": [], "unresolved_claim_ids": [],
        "round_summary": "", "round_goal": "",
    }
    risk = {
        "aggressive_history": [], "conservative_history": [], "neutral_history": [],
        "history": [], "judge_decision": "", "claims": [],
        "focus_claim_ids": [], "open_claim_ids": [], "resolved_claim_ids": [],
        "unresolved_claim_ids": [], "round_summary": "", "round_goal": "",
    }
    return {
        "company_of_interest": "688469",
        "trade_date": "2026-09-04",
        "market_report": "❌ 数据缺口（emoji 回归）",
        "sentiment_report": "⚠️ 中性",
        "news_report": "news",
        "fundamentals_report": "fund",
        "macro_report": "macro",
        "smart_money_report": "smart",
        "volume_price_report": "vol",
        "investment_plan": "plan",
        "trader_investment_plan": "trader",
        "final_trade_decision": "SELL ✅",
        "investment_debate_state": debate,
        "risk_debate_state": risk,
        "risk_feedback_state": {},
    }


def test_log_state_writes_utf8_with_emoji(tmp_path, monkeypatch):
    ta = TradingAgentsGraph.__new__(TradingAgentsGraph)
    ta.ticker = "688469"
    ta.log_states_dict = {}
    monkeypatch.chdir(tmp_path)
    ta._log_state("2026-09-04", _nested_state_skeleton())
    fp = tmp_path / "eval_results/688469/TradingAgentsStrategy_logs/full_states_log_2026-09-04.json"
    assert fp.exists()
    raw = fp.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    # _log_state 用 ensure_ascii=True，emoji 以 \uXXXX 转义存储；解码后必须还原
    assert "❌" in parsed["2026-09-04"]["market_report"]
    assert "✅" in parsed["2026-09-04"]["final_trade_decision"]


def test_log_state_dual_writes_utf8_with_emoji(tmp_path, monkeypatch):
    ta = TradingAgentsGraph.__new__(TradingAgentsGraph)
    ta.ticker = "688469"
    ta.log_states_dict = {}
    monkeypatch.chdir(tmp_path)
    short = {"company_of_interest": "688469", "final_trade_decision": "SELL ✅"}
    ta._log_state_dual("2026-09-04", short, {}, {"raw_query": ""})
    fp = tmp_path / "eval_results/688469/TradingAgentsStrategy_logs/dual_horizon_2026-09-04.json"
    assert fp.exists()
    raw = fp.read_text(encoding="utf-8")
    assert "✅" in raw
    assert json.loads(raw)