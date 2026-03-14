import functools
import time
import json
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.agents.utils.context_utils import build_agent_context_view


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        if past_memories:
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            past_memory_str = "No past memories found."

        config = get_config()
        context_view = build_agent_context_view(state, "trader")
        context = {
            "role": "user",
            "content": get_prompt("trader_user_prompt", config=config).format(
                company_name=company_name,
                investment_plan=investment_plan,
                instrument_context_summary=context_view["instrument_context_summary"],
                market_context_summary=context_view["market_context_summary"],
                user_context_summary=context_view["user_context_summary"],
            ),
        }

        messages = [
            {
                "role": "system",
                "content": get_prompt("trader_system_prompt", config=config).format(
                    past_memory_str=past_memory_str,
                    market_context_summary=context_view["market_context_summary"],
                    user_context_summary=context_view["user_context_summary"],
                ),
            },
            context,
        ]

        result = llm.invoke(messages)

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
