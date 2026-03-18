from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context
from tradingagents.agents.utils.agent_utils import get_seat_history
from tradingagents.agents.utils.debate_utils import (
    format_claim_subset_for_prompt,
    format_round_summary_for_prompt,
    update_debate_state,
)


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


def create_smart_money_analyst(llm, data_collector=None):
    # Bind tools for ReAct
    llm_with_tools = llm.bind_tools([get_seat_history])

    def _safe(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    def smart_money_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = state.get("horizon", "short")
        
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
        round_goal = gt_debate_state.get("round_goal", "分析主力意图")

        config = get_config()
        system_message_template = get_prompt("smart_money_system_message", config=config) or ""
        
        # Fetch quant data
        pool = data_collector.get(ticker, current_date) if data_collector else None
        if pool is not None:
            fund_flow = pool.get("fund_flow_individual", "无数据")
            lhb = pool.get("lhb", "无数据")
            volume = pool.get("indicators", {}).get("vwma", "无数据")
        else:
            from tradingagents.agents.utils.agent_utils import (
                get_individual_fund_flow, get_lhb_detail, get_indicators,
            )
            fund_flow = _safe(get_individual_fund_flow, {"symbol": ticker})
            lhb = _safe(get_lhb_detail, {"symbol": ticker, "date": current_date})
            volume = _safe(get_indicators, {
                "symbol": ticker, "indicator": "volume",
                "curr_date": current_date, "look_back_days": 20,
            })

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
            SystemMessage(content=system_content),
            HumanMessage(content=(
                f"请基于以下主力数据进行博弈分析：\n\n"
                f"【近5日主力资金净流向】\n{fund_flow}\n\n"
                f"【龙虎榜数据】\n{lhb}\n\n"
                f"【成交量指标(vwma)】\n{volume}"
            )),
        ]

        # Handle ReAct messages
        react_messages = []
        for msg in state.get("messages", []):
            if isinstance(msg, AIMessage) and msg.name == "Smart Money Analyst":
                react_messages.append(msg)
            elif isinstance(msg, ToolMessage) and msg.name == "get_seat_history":
                react_messages.append(msg)
        
        messages_to_invoke = messages + react_messages

        print(f"[Smart Money Analyst] Invoking LLM (history: {len(react_messages)} msgs)...")
        result = llm_with_tools.invoke(messages_to_invoke)
        result.name = "Smart Money Analyst"

        if result.tool_calls:
            return {"messages": [result]}
        else:
            print(f"[Smart Money Analyst] DONE {ticker}, report length={len(result.content)}")
            
            # Update debate state
            new_gt_state = update_debate_state(
                gt_debate_state,
                result.content,
                speaker="Smart Money",
                state_key="GT_DEBATE_STATE",
                claim_prefix="GT",
                domain="game_theory",
                speaker_field="current_speaker"
            )
            
            verdict, confidence = _extract_verdict(result.content)
            
            return {
                "smart_money_report": result.content,
                "game_theory_debate_state": new_gt_state,
                "analyst_traces": [{
                    "agent": "smart_money_analyst",
                    "horizon": horizon,
                    "data_window": "近期可用",
                    "key_finding": f"主力博弈结论：{verdict}",
                    "verdict": verdict,
                    "confidence": confidence,
                }],
            }

    return smart_money_analyst_node
