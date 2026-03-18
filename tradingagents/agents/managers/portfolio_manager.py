import time
import json
import functools
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.agents.utils.context_utils import build_agent_context_view
from tradingagents.agents.utils.debate_utils import extract_tagged_json

def create_portfolio_manager(llm):
    def portfolio_manager_node(state, name):
        config = get_config()
        
        # Build context views
        context_view = build_agent_context_view(state, "portfolio_manager")
        
        # Prepare inputs for PM
        trader_plan = state.get("trader_investment_plan", "No trader plan provided.")
        risk_judge_verdict = state.get("final_trade_decision", "No risk judge verdict provided.")
        
        system_prompt = get_prompt("portfolio_manager_prompt", config=config).format(
            trader_plan=trader_plan,
            risk_judge_verdict=risk_judge_verdict,
            market_context_summary=context_view["market_context_summary"],
            user_context_summary=context_view["user_context_summary"]
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please generate the final portfolio allocation for {state['company_of_interest']}."}
        ]
        
        print(f"[{name}] Generating final portfolio allocation...")
        start_time = time.time()
        response = llm.invoke(messages)
        end_time = time.time()
        print(f"[{name}] DONE, allocation report generated in {end_time - start_time:.2f}s")
        
        # Extract structured allocation details
        allocation_details = extract_tagged_json(response.content, "ALLOCATION")
        
        return {
            "portfolio_report": response.content,
            "allocation_details": allocation_details or {},
            "sender": name
        }

    return functools.partial(portfolio_manager_node, name="Portfolio Manager")
