from langchain_core.messages import HumanMessage
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import parse_intent
import time
import functools

def create_retail_investor_analyst(llm, tools):
    """
    Creates a Retail Investor Analyst node that focuses on market heat and retail FOMO/Panic.
    Uses get_zt_pool and get_hot_stocks_xq.
    """
    llm_with_tools = llm.bind_tools(tools)

    def retail_investor_analyst_node(state, name):
        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        config = get_config()

        system_message = get_prompt("retail_investor_system_message", config=config)

        # Build initial messages
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"分析标的 {ticker} 在 {trade_date} 附近的散户情绪与市场热度。请务必核查今日涨停池和热搜数据。"}
        ]

        # Simple ReAct loop
        print(f"[{name}] Invoking LLM (history: {len(messages)} msgs)...")
        start_time = time.time()
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        # Handle tool calls if any
        if response.tool_calls:
            print(f"[{name}] Tool call requested: {response.tool_calls}")
            # Note: The actual tool execution happens in the ToolNode in the graph.
            # We just return the AI message to trigger the routing.
        
        end_time = time.time()
        
        # If no tool calls, it means it's done
        if not response.tool_calls:
             print(f"[{name}] DONE {ticker}, report length={len(response.content)}")
             return {
                "retail_report": response.content,
                "sender": name,
                "messages": [response],
                "analyst_traces": [{
                    "agent": name,
                    "horizon": state.get("horizon", "short"),
                    "data_window": "当前情绪",
                    "key_finding": f"散户情绪分析已完成",
                    "verdict": "情绪指标已提取",
                    "confidence": "高",
                }],
            }
        
        return {
            "messages": [response],
            "sender": name
        }

    return functools.partial(retail_investor_analyst_node, name="Retail Investor Analyst")
