from langchain_core.tools import tool

from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)
from tradingagents.agents.utils.game_theory_tools import (
    get_board_fund_flow,
    get_individual_fund_flow,
    get_lhb_detail,
    get_zt_pool,
    get_hot_stocks_xq,
)

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        company = state.get("company_of_interest", "")
        trade_date = state.get("trade_date", "")
        # Keep concise but explicit context so next agent doesn't ask for missing task/date.
        placeholder_text = (
            f"Continue analysis for symbol {company} on {trade_date}. "
            "Use available tools and context; do not ask the user for missing task details."
        ).strip()
        placeholder = HumanMessage(content=placeholder_text)

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        

@tool
def get_seat_history(seat_name: str, limit: int = 10) -> str:
    """Queries the historical performance and style of a specific trading seat."""
    return f"Seat {seat_name} history: [Simulated] Frequently appears in hot stocks, 2-day exit pattern."


@tool
def get_industry_peers(symbol: str) -> str:
    """Retrieves a list of industry peers, competitors, and supply chain entities for a given ticker."""
    # Simplified mock for demonstration. In a real system, we might use akshare stock_board_industry queries.
    return f"Peers for {symbol}: [Simulated] Competitor A, Supplier B, Downstream C."

