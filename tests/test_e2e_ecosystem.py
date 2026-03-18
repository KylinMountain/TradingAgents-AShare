import pytest
from tradingagents.graph.trading_graph import TradingAgentsGraph

def test_ecosystem_react_loop():
    graph = TradingAgentsGraph(selected_analysts=["ecosystem"])
    
    user_intent = {
        "raw_query": "分析600519，看下它的上下游",
        "ticker": "600519",
        "horizons": ["short"],
        "focus_areas": ["生态链"],
        "specific_questions": [],
        "user_context": {},
    }
    
    state = graph.propagator.create_initial_state(
        "600519", "2024-01-15", user_intent=user_intent, horizon="short"
    )
    args = graph.propagator.get_graph_args()
    args["config"]["configurable"] = {"thread_id": "test_e2e_ecosystem"}
    
    final_state = graph.graph.invoke(state, **args)
    assert "ecosystem_report" in final_state
    
    messages = final_state.get("messages", [])
    tool_calls = [m for m in messages if hasattr(m, "name") and m.name == "get_industry_peers"]
    print(f"Tool calls made: {len(tool_calls)}")