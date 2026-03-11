from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.agents.utils.agent_utils import (
    get_individual_fund_flow,
    get_lhb_detail,
    get_indicators,
)
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt


def create_smart_money_analyst(llm):
    def _invoke_tool(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"{tool.name} 调用失败：{type(exc).__name__}: {exc}"

    def smart_money_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        print(f"[Smart Money Analyst] START {ticker} {current_date}")
        config = get_config()
        system_message = get_prompt("smart_money_system_message", config=config)

        fund_flow = _invoke_tool(get_individual_fund_flow, {"symbol": ticker})
        lhb = _invoke_tool(get_lhb_detail, {"symbol": ticker, "date": current_date})
        volume = _invoke_tool(get_indicators, {
            "symbol": ticker,
            "indicator": "volume",
            "curr_date": current_date,
            "look_back_days": 20,
        })

        messages = [
            SystemMessage(
                content=(
                    system_message
                    + "\n\n你已经拿到资金流向和成交量数据。现在只基于这些数据写报告，"
                    "不要输出工具调用，请全程使用中文。"
                )
            ),
            HumanMessage(
                content=(
                    f"请分析 {ticker} 在 {current_date} 的主力资金行为。\n\n"
                    f"【近5日主力资金净流向】\n{fund_flow}\n\n"
                    f"【龙虎榜数据】\n{lhb}\n\n"
                    f"【近20日成交量数据】\n{volume}"
                )
            ),
        ]

        result = llm.invoke(messages)
        print(f"[Smart Money Analyst] DONE {ticker}, report length={len(result.content)}")
        return {"smart_money_report": result.content}

    return smart_money_analyst_node
