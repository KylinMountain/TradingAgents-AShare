from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.agents.utils.agent_utils import get_news, get_zt_pool, get_hot_stocks_xq
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt


def create_social_media_analyst(llm):
    def _invoke_tool(tool, payload):
        try:
            return tool.invoke(payload)
        except Exception as exc:
            return f"{tool.name} 调用失败：{type(exc).__name__}: {exc}"

    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        config = get_config()
        system_message = get_prompt("social_system_message", config=config)

        end_dt = datetime.strptime(current_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=7)
        news_text = _invoke_tool(
            get_news,
            {
                "ticker": ticker,
                "start_date": start_dt.strftime("%Y-%m-%d"),
                "end_date": current_date,
            },
        )

        zt_data = _invoke_tool(get_zt_pool, {"date": current_date})
        hot_stocks = _invoke_tool(get_hot_stocks_xq, {})

        messages = [
            SystemMessage(
                content=(
                    system_message
                    + "\n\n你已经拿到近一周舆情近似数据。现在只基于这些结果写报告，"
                    "不要继续请求工具，不要输出 <longcat_tool_call>、XML、JSON 或伪函数调用。"
                    "请全程使用中文。"
                )
            ),
            HumanMessage(
                content=(
                    f"以下是 {ticker} 在 {current_date} 的舆情近似资料。"
                    "请严格基于这些资料输出舆情分析报告。\n\n"
                    f"【get_news】\n{news_text}\n"
                    f"\n【涨停池数据】\n{zt_data}\n"
                    f"\n【雪球热门股票】\n{hot_stocks}\n"
                )
            ),
        ]

        result = llm.invoke(messages)
        return {
            "sentiment_report": result.content,
        }

    return social_media_analyst_node
