from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context
from tradingagents.agents.utils.agent_utils import get_industry_peers, get_news


def _extract_verdict(text):
    import re, json
    m = re.search(r'<!--\s*VERDICT:\s*(\{.*?\})\s*-->', text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(1))
            return d.get("direction", "中性"), "中"
        except Exception:
            pass
    return "中性", "低"


def create_ecosystem_analyst(llm, data_collector=None):
    # This analyst uses ReAct loop to query peers and news about peers.
    llm_with_tools = llm.bind_tools([get_industry_peers, get_news])

    def ecosystem_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "short")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("ecosystem_system_message", config=config) or ""
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, "ecosystem")

        # Base context messages
        base_messages = [
            SystemMessage(content=(
                horizon_ctx + system_message
                + "\n\n请严格基于提供的量化数据输出分析，全程使用中文。"
            )),
            HumanMessage(content=(
                f"请分析 {ticker} 在 {current_date} 所处的产业生态（上下游与竞争对手）。\n"
                f"你可以先调用 get_industry_peers 获取相关公司列表，然后再调用 get_news 获取它们的最新动向，以此来验证 {ticker} 的逻辑。"
            )),
        ]

        # Extract previous ReAct messages for this specific node
        react_messages = []
        for msg in state.get("messages", []):
            if isinstance(msg, AIMessage) and msg.name == "Ecosystem Analyst":
                react_messages.append(msg)
            elif isinstance(msg, ToolMessage) and msg.name in ["get_industry_peers", "get_news"]:
                # To be precise, we only want tools called by this agent, but LangGraph will match them.
                react_messages.append(msg)

        messages_to_invoke = base_messages + react_messages

        print(f"[Ecosystem Analyst] Invoking LLM (history: {len(react_messages)} msgs)...")
        result = llm_with_tools.invoke(messages_to_invoke)
        result.name = "Ecosystem Analyst"

        if result.tool_calls:
            print(f"[Ecosystem Analyst] Tool call requested: {result.tool_calls}")
            return {"messages": [result]}
        else:
            print(f"[Ecosystem Analyst] DONE {ticker}, report length={len(result.content)}")
            verdict, confidence = _extract_verdict(result.content)
            return {
                "ecosystem_report": result.content,
                "analyst_traces": [{
                    "agent": "ecosystem_analyst",
                    "horizon": horizon,
                    "data_window": "当前节点",
                    "key_finding": f"生态分析结论：{verdict}",
                    "verdict": verdict,
                    "confidence": confidence,
                }],
            }

    return ecosystem_analyst_node
