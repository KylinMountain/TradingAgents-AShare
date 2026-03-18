import pytest
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.agents.utils.agent_states import RiskFeedbackState

def test_risk_feedback_loop():
    # 1. 初始化图
    graph = TradingAgentsGraph(selected_analysts=["market"])
    
    # 2. 构造一个包含 Risk Judge 打回信号的状态
    user_intent = {
        "raw_query": "买入 600519",
        "ticker": "600519",
        "horizons": ["short"],
        "user_context": {"max_loss_pct": 5.0},
    }
    
    state = graph.propagator.create_initial_state(
        "600519", "2024-01-15", user_intent=user_intent, horizon="short"
    )
    
    # 模拟已经被 Risk Judge 打回的状态
    state["risk_feedback_state"] = {
        "retry_count": 1,
        "max_retries": 3,
        "revision_required": True,
        "latest_risk_verdict": "revise",
        "hard_constraints": ["止损比例必须设置在3%以内"],
        "revision_reason": "原计划止损过宽",
    }
    state["investment_plan"] = "多头逻辑：基本面强劲"
    state["trader_investment_plan"] = "计划买入100股，止损10%"
    
    # 3. 直接调用 Trader 逻辑验证其是否能识别反馈
    from tradingagents.agents.trader.trader import create_trader
    
    # 我们需要模拟一个 LLM 和一个 Memory
    class MockLLM:
        def invoke(self, messages):
            class MockResponse:
                def __init__(self):
                    self.content = "修订后的计划：买入 600519，止损 3%"
            return MockResponse()
            
    class MockMemory:
        def get_memories(self, context, n_matches=2):
            return []
            
    trader_node_func = create_trader(MockLLM(), MockMemory())
    
    # Trader 节点是一个 partial 函数，实际执行时接收 state
    result = trader_node_func(state)
    
    assert "trader_investment_plan" in result
    # 检查风险反馈是否被重置（表示 Trader 已经处理了这次修订要求）
    assert result["risk_feedback_state"]["revision_required"] is False
    print("Trader successfully processed risk feedback and generated revision.")

if __name__ == "__main__":
    test_risk_feedback_loop()
