import pytest
from tradingagents.graph.trading_graph import TradingAgentsGraph

def test_game_theory_debate_loop():
    # 1. 初始化图，只选主力与散户，以便测试博弈辩论线
    # 注意：我们的 graph 逻辑要求 selected_analysts 必须包含对应的 analyst_type 字符串
    graph = TradingAgentsGraph(selected_analysts=["smart_money", "retail"])
    
    # 2. 构造意图
    user_intent = {
        "raw_query": "分析 600519 的筹码博弈",
        "ticker": "600519",
        "horizons": ["short"]
    }
    
    # 3. 创建初始状态
    state = graph.propagator.create_initial_state(
        "600519", "2024-01-15", user_intent=user_intent, horizon="short",
        selected_analysts=["smart_money", "retail"]
    )
    
    # 4. 模拟已完成的并行分析，进入 GT 辩论
    state["smart_money_report"] = "初步观察：主力筹码锁定良好。"
    state["retail_report"] = "初步观察：散户热度一般。"
    
    # 5. 获取编译后的图
    compiled_graph = graph.graph_setup.setup_graph(selected_analysts=["smart_money", "retail"])
    
    # 6. 直接调用节点逻辑验证其是否能正确更新博弈状态
    from tradingagents.agents.analysts.smart_money_analyst import create_smart_money_analyst
    from tradingagents.agents.analysts.retail_investor_analyst import create_retail_investor_analyst
    
    class MockLLM:
        def __init__(self, content):
            self.content = content
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            class MockResponse:
                def __init__(self, c):
                    self.content = c
                    self.tool_calls = []
            res = MockResponse(self.content)
            return res

    # 第一轮：Smart Money 发言
    sm_logic = create_smart_money_analyst(MockLLM("<!-- DEBATE_STATE: {\"responded_claim_ids\": [], \"new_claims\": [{\"claim\": \"主力收割\"}], \"round_summary\": \"主力进攻\"} -->"))
    res1 = sm_logic(state)
    assert "game_theory_debate_state" in res1
    assert res1["game_theory_debate_state"]["count"] == 1
    assert res1["game_theory_debate_state"]["current_speaker"] == "Smart Money Analyst"
    
    # 更新状态模拟流向 Retail
    state.update(res1)
    
    # 第二轮：Retail 反应
    retail_logic = create_retail_investor_analyst(MockLLM("<!-- DEBATE_STATE: {\"responded_claim_ids\": [\"GT-1\"], \"new_claims\": [], \"round_summary\": \"散户防御\"} -->"), [])
    res2 = retail_logic(state)
    assert res2["game_theory_debate_state"]["count"] == 2
    assert res2["game_theory_debate_state"]["current_speaker"] == "Retail Investor Analyst"
    
    print("Game Theory Debate Node logic (Smart Money <-> Retail) verified.")

if __name__ == "__main__":
    test_game_theory_debate_loop()
