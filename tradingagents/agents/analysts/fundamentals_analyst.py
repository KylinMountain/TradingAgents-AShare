import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context
from tradingagents.agents.utils.agent_states import current_tracker_var, extract_verdict


def create_fundamentals_analyst(llm, data_collector=None):
    async def _safe(tool, payload):
        try:
            return await asyncio.to_thread(tool.invoke, payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    async def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        horizon = "medium"  # 基本面固定中长期视角
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("fundamentals_system_message", config=config)
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, agent_type="fundamentals")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            outputs = {k: pool.get(k, "无数据") for k in
                       ["fundamentals", "balance_sheet", "cashflow", "income_statement"]}
            outputs["research_reports"] = pool.get("research_reports", "无数据")
            outputs["shareholder_changes"] = pool.get("shareholder_changes", "无数据")
            outputs["restricted_release"] = pool.get("restricted_release", "无数据")
            outputs["pledge_ratio"] = pool.get("pledge_ratio", "无数据")
            outputs["shareholder_count"] = pool.get("shareholder_count", "无数据")
            outputs["dividend_history"] = pool.get("dividend_history", "无数据")
            outputs["f10_detail"] = pool.get("f10_detail", "无数据")
        else:
            from tradingagents.agents.utils.agent_utils import (
                get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement,
                get_research_reports, get_shareholder_changes, get_restricted_release, get_pledge_ratio,
            )
            tasks = {
                "fundamentals": _safe(get_fundamentals, {"ticker": ticker, "curr_date": current_date}),
                "balance_sheet": _safe(get_balance_sheet, {"ticker": ticker, "freq": "quarterly", "curr_date": current_date}),
                "cashflow": _safe(get_cashflow, {"ticker": ticker, "freq": "quarterly", "curr_date": current_date}),
                "income_statement": _safe(get_income_statement, {"ticker": ticker, "freq": "quarterly", "curr_date": current_date}),
                "research_reports": _safe(get_research_reports, {"symbol": ticker}),
                "shareholder_changes": _safe(get_shareholder_changes, {"symbol": ticker}),
                "restricted_release": _safe(get_restricted_release, {"symbol": ticker}),
                "pledge_ratio": _safe(get_pledge_ratio, {"date": current_date}),
            }
            keys = list(tasks.keys())
            results = await asyncio.gather(*[tasks[k] for k in keys])
            outputs = dict(zip(keys, results))
            # 确保非工具字段也有默认值
            for _k in ("shareholder_count", "dividend_history", "f10_detail"):
                outputs.setdefault(_k, "无数据")

        messages = [
            SystemMessage(content=system_message + "\n\n请全程使用中文。"),
            HumanMessage(content=(
                horizon_ctx + "\n"
                f"以下是 {ticker} 在 {current_date} 的基本面资料。\n\n"
                f"【get_fundamentals】\n{outputs['fundamentals']}\n\n"
                f"【get_balance_sheet】\n{outputs['balance_sheet']}\n\n"
                f"【get_cashflow】\n{outputs['cashflow']}\n\n"
                f"【get_income_statement】\n{outputs['income_statement']}\n\n"
                f"【机构研报】\n{outputs['research_reports']}\n\n"
                f"【股东增减持】\n{outputs['shareholder_changes']}\n\n"
                f"【限售解禁】\n{outputs['restricted_release']}\n\n"
                f"【股权质押】\n{outputs['pledge_ratio']}\n\n"
                f"【股东户数变化（筹码集中度）】\n{outputs['shareholder_count']}\n\n"
                f"【分红送转历史】\n{outputs['dividend_history']}\n\n"
                f"【F10公司资料】\n{outputs['f10_detail']}\n"
            )),
        ]

        # ── 实现 Token 级流式输出 ──────────────────
        tracker = current_tracker_var.get()
        full_content = ""
        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_content += content
            if tracker:
                tracker._emit_token("Fundamentals Analyst", "fundamentals_report", content)

        verdict, confidence = extract_verdict(full_content)
        return {
            "fundamentals_report": full_content,
            "analyst_traces": [{
                "agent": "fundamentals_analyst",
                "horizon": horizon,
                "data_window": "财报周期",
                "key_finding": f"基本面分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return fundamentals_analyst_node
