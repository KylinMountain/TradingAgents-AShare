from langchain_core.messages import HumanMessage

from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.agents.utils.debate_utils import extract_tagged_json, strip_tagged_json


def create_game_theory_manager(llm):
    def game_theory_manager_node(state):
        smart_money_report = state.get("smart_money_report", "无主力资金数据")
        sentiment_report = state.get("sentiment_report", "无情绪数据")
        print(f"[Game Theory Manager] START smart_money={'有' if smart_money_report != '无主力资金数据' else '无'}, sentiment={'有' if sentiment_report != '无情绪数据' else '无'}")
        config = get_config()

        prompt_template = get_prompt("game_theory_manager_prompt", config=config)
        if not prompt_template:
            print("[Game Theory Manager] ERROR: Prompt template not found")
            return {"game_theory_report": "博弈分析提示词模板缺失，无法生成报告。"}

        prompt = prompt_template.format(
            smart_money_report=smart_money_report,
            sentiment_report=sentiment_report,
        )

        result = llm.invoke(prompt)
        structured_signals = extract_tagged_json(result.content, "GAME_THEORY")
        cleaned_report = strip_tagged_json(result.content, "GAME_THEORY")
        print(f"[Game Theory Manager] DONE, report length={len(result.content)}")
        return {
            "game_theory_report": cleaned_report,
            "game_theory_signals": structured_signals,
        }

    return game_theory_manager_node
