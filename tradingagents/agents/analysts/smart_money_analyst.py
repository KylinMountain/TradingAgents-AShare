import asyncio

from langchain_core.messages import HumanMessage, SystemMessage
from tradingagents.dataflows.config import get_config
from tradingagents.prompts import get_prompt
from tradingagents.graph.intent_parser import build_horizon_context
from tradingagents.agents.utils.agent_states import current_tracker_var, extract_verdict


def create_smart_money_analyst(llm, data_collector=None):
    async def _safe(tool, payload):
        try:
            return await asyncio.to_thread(tool.invoke, payload)
        except Exception as exc:
            return f"调用失败：{exc}"

    async def smart_money_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        print(f"[Smart Money Analyst] START {ticker} {current_date}")
        horizon = "short"  # 资金面固定短期视角
        from datetime import datetime, timedelta
        end_dt = datetime.strptime(current_date, "%Y-%m-%d")
        week_ago = (end_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        user_intent = state.get("user_intent") or {}
        focus_areas = user_intent.get("focus_areas", [])
        specific_questions = user_intent.get("specific_questions", [])

        config = get_config()
        system_message = get_prompt("smart_money_system_message", config=config) or ""
        horizon_ctx = build_horizon_context(horizon, focus_areas, specific_questions, agent_type="smart_money")

        pool = data_collector.get(ticker, current_date) if data_collector else None

        if pool is not None:
            fund_flow = pool.get("fund_flow_individual", "无数据")
            lhb = pool.get("lhb", "无数据")
            volume = pool.get("indicators", {}).get("vwma", "无数据")
            hsgt_individual = pool.get("hsgt_individual", "无数据")
            hsgt_flow = pool.get("hsgt_flow", "无数据")
            block_trades = pool.get("block_trades", "无数据")
            lhb_inst = pool.get("lhb_institution_stats", "无数据")
            lhb_seats = pool.get("lhb_active_seats", "无数据")
        else:
            from tradingagents.agents.utils.agent_utils import (
                get_individual_fund_flow, get_lhb_detail, get_indicators,
                get_hsgt_individual, get_hsgt_flow, get_block_trades,
                get_lhb_institution_stats, get_lhb_active_seats,
            )

            # Parallelize fallback fetches
            results = await asyncio.gather(
                _safe(get_individual_fund_flow, {"symbol": ticker}),
                _safe(get_lhb_detail, {"symbol": ticker, "date": current_date}),
                _safe(get_indicators, {
                    "symbol": ticker, "indicator": "vwma",
                    "curr_date": current_date, "look_back_days": 20,
                }),
                _safe(get_hsgt_individual, {"symbol": ticker}),
                _safe(get_hsgt_flow, {}),
                _safe(get_block_trades, {"symbol": ticker, "start_date": week_ago, "end_date": current_date}),
                _safe(get_lhb_institution_stats, {"symbol": ticker, "start_date": week_ago, "end_date": current_date}),
                _safe(get_lhb_active_seats, {"start_date": week_ago, "end_date": current_date}),
            )
            fund_flow, lhb, volume, hsgt_individual, hsgt_flow, block_trades, lhb_inst, lhb_seats = results

        messages = [
            SystemMessage(content=(
                system_message
                + "\n\n请严格基于提供的量化数据输出分析，全程使用中文。"
            )),
            HumanMessage(content=(
                horizon_ctx + "\n"
                f"请分析 {ticker} 在 {current_date} 的主力资金行为。\n\n"
                f"【近5日主力资金净流向】\n{fund_flow}\n\n"
                f"【龙虎榜数据】\n{lhb}\n\n"
                f"【成交量指标(vwma)】\n{volume}\n\n"
                f"【北向资金持仓（个股）】\n{hsgt_individual}\n\n"
                f"【北向资金整体净流入】\n{hsgt_flow}\n\n"
                f"【大宗交易明细】\n{block_trades}\n\n"
                f"【龙虎榜机构买卖统计】\n{lhb_inst}\n\n"
                f"【龙虎榜活跃营业部】\n{lhb_seats}"
            )),
        ]

        # ── 实现 Token 级流式输出 ──────────────────
        tracker = current_tracker_var.get()
        full_content = ""
        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_content += content
            if tracker:
                tracker._emit_token("Smart Money Analyst", "smart_money_report", content)

        print(f"[Smart Money Analyst] DONE {ticker}, report length={len(full_content)}")
        verdict, confidence = extract_verdict(full_content)
        return {
            "smart_money_report": full_content,
            "analyst_traces": [{
                "agent": "smart_money_analyst",
                "horizon": horizon,
                "data_window": "近期可用",
                "key_finding": f"主力资金分析结论：{verdict}",
                "verdict": verdict,
                "confidence": confidence,
            }],
        }

    return smart_money_analyst_node
