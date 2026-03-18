from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.agents.utils.debate_utils import (
    format_claim_subset_for_prompt,
    format_round_summary_for_prompt,
    update_debate_state,
)
import time
import functools

def create_retail_investor_analyst(llm, tools):
    """
    Creates a Retail Investor Analyst node that simulates the crowd and debates with smart money.
    """
    llm_with_tools = llm.bind_tools(tools)

    def retail_investor_analyst_node(state, name):
        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        
        # Debate integration
        gt_debate_state = state.get("game_theory_debate_state", {})
        history = gt_debate_state.get("history", "博弈尚未开始。")
        current_response = gt_debate_state.get("current_response", "无。")
        
        # Prepare debate context
        from tradingagents.agents.utils.debate_utils import format_claims_for_prompt
        claims_text = format_claims_for_prompt(gt_debate_state.get("claims", []))
        focus_claims_text = format_claim_subset_for_prompt(
            gt_debate_state.get("claims", []), 
            gt_debate_state.get("focus_claim_ids", [])
        )
        unresolved_claims_text = format_claim_subset_for_prompt(
            gt_debate_state.get("claims", []), 
            gt_debate_state.get("unresolved_claim_ids", [])
        )
        round_summary = format_round_summary_for_prompt(gt_debate_state.get("round_summary", ""))
        round_goal = gt_debate_state.get("round_goal", "模拟散户心理")

        config = get_config()
        system_message_template = get_prompt("retail_investor_system_message", config=config)

        # Build prompt
        system_content = system_message_template.format(
            history=history,
            current_response=current_response,
            claims_text=claims_text,
            focus_claims_text=focus_claims_text,
            unresolved_claims_text=unresolved_claims_text,
            round_summary=round_summary,
            round_goal=round_goal
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"分析标的 {ticker} 的散户情绪。当前主力已出招，请给出散户的直观体感与博弈反应。"}
        ]

        # Handle ReAct messages
        react_messages = []
        for msg in state.get("messages", []):
            if isinstance(msg, AIMessage) and msg.name == name:
                react_messages.append(msg)
            elif isinstance(msg, ToolMessage) and (msg.name == "get_zt_pool" or msg.name == "get_hot_stocks_xq"):
                react_messages.append(msg)

        messages_to_invoke = messages + react_messages

        print(f"[{name}] Invoking LLM (history: {len(react_messages)} msgs)...")
        start_time = time.time()
        response = llm_with_tools.invoke(messages_to_invoke)
        response.name = name
        
        if response.tool_calls:
            return {"messages": [response]}
        else:
            print(f"[{name}] DONE {ticker}, report length={len(response.content)}")
            
            # Update debate state
            new_gt_state = update_debate_state(
                gt_debate_state,
                response.content,
                speaker="Retail",
                state_key="GT_DEBATE_STATE",
                claim_prefix="GT",
                domain="game_theory",
                speaker_field="current_speaker"
            )
            
            return {
                "retail_report": response.content,
                "game_theory_debate_state": new_gt_state,
                "sender": name,
                "analyst_traces": [{
                    "agent": name,
                    "horizon": state.get("horizon", "short"),
                    "data_window": "当前情绪",
                    "key_finding": f"散户情绪博弈已完成",
                    "verdict": "情绪指标已提取",
                    "confidence": "高",
                }],
            }

    return functools.partial(retail_investor_analyst_node, name="Retail Investor Analyst")
