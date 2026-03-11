from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.agents.utils.agent_utils import get_board_fund_flow, get_news
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt


def create_macro_analyst(llm):
    def _invoke_tool(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"{tool.name} 调用失败：{type(exc).__name__}: {exc}"

    def macro_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        print(f"[Macro Analyst] START {ticker} {current_date}")
        config = get_config()
        system_message = get_prompt("macro_system_message", config=config)

        board_flow = _invoke_tool(get_board_fund_flow, {"symbol": ticker})

        end_dt = datetime.strptime(current_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=7)
        recent_news = _invoke_tool(get_news, {
            "ticker": ticker,
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": current_date,
        })

        messages = [
            SystemMessage(
                content=(
                    system_message
                    + "\n\n你已经拿到板块资金流向和新闻数据。现在只基于这些数据写报告，"
                    "不要输出工具调用，请全程使用中文。"
                )
            ),
            HumanMessage(
                content=(
                    f"请分析 {ticker} 在 {current_date} 的宏观与板块环境。\n\n"
                    f"【今日行业板块资金流向】\n{board_flow}\n\n"
                    f"【近7日相关新闻】\n{recent_news}"
                )
            ),
        ]

        result = llm.invoke(messages)
        print(f"[Macro Analyst] DONE {ticker}, report length={len(result.content)}")
        return {"macro_report": result.content}

    return macro_analyst_node
