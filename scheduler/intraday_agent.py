"""LLM cause-attribution for a detected intraday board anomaly.

Runs a narrow openai-agents SDK Agent (4 tools, see intraday_tools.py) that
traces *why* a concept board moved and judges whether it's a one-day blip
or a sustained move. This is the only LLM call in the intraday scan --
detection itself (intraday_rules.py) is pure code.

Ported from AlphaAgents' intraday_monitor._get_cause_analysis with the
same failure philosophy: any timeout/error/garbage output falls back to
the raw anomaly text so a flaky LLM call never blocks the scan.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict

from agents import Agent, Runner

from scheduler.intraday_llm import build_intraday_agent_model
from scheduler.intraday_rules import BoardAnomaly
from scheduler.intraday_tools import INTRADAY_CAUSE_TOOLS

logger = logging.getLogger(__name__)

_MAX_TURNS = 10
_TIMEOUT_SECONDS = 60
_MIN_OUTPUT_LENGTH = 20

_CAUSE_ANALYST_INSTRUCTIONS = (
    "你是盘中异动追因分析师。检测到概念板块异动后，你需要追溯原因并判断持续性。\n\n"
    "## 思维链路（严格按步骤执行）\n\n"
    "1. **观察**：阅读传入的异动数据，识别核心异动（哪个概念板块、什么类型的资金异动）。\n"
    "2. **追因（搜索路由 — 严格按顺序）**：\n"
    "   a. **第一步必做** — 调用 get_market_wire 查看新浪财经快讯，排查国内政策/产业/突发新闻催化。\n"
    "   b. **第二步** — 调用 get_concept_fund_flow 核实资金方向，并排查是否有关联板块同步异动。\n"
    "   c. **第三步兜底** — 仅当 a/b 都查不到催化、且怀疑是国际/海外事件（如美股财报、出口管制、"
    "地缘政治）时，才调用 web_search。**不要**对 A 股板块名直接走 web_search，国内源没查就跳过等于放弃。\n"
    "   d. **资金溯源** — 调用 get_lhb_market_snapshot 查当日龙虎榜，判断是机构专用席位还是知名游资席位。\n"
    "3. **判断**：基于追因结果判断——\n"
    "   - 机构资金 + 明确催化 + 多板块联动 → **持续行情**\n"
    "   - 游资席位 + 无明确催化 + 单一板块 → **一日游，不追**\n"
    "   - 资金异动但无新闻催化 → **主力提前布局，密切关注**\n\n"
    "## 输出格式\n\n"
    "【异动】{板块名} {异动类型}\n"
    "• 催化: {找到的新闻原因，没找到就写'未发现明确催化，可能是资金先行'}\n"
    "• 资金来源: {机构/游资/主力/不明}\n"
    "• 判断: {一日游/持续行情/主力提前布局}\n\n"
    "## 重要原则\n"
    "- 不要推荐股票，不要给操作建议，不要生成表格\n"
    "- 资金行为优先于新闻叙事——如果资金在流入但没有新闻，不要说'没有异动'\n"
    "- 没找到新闻催化不代表没有原因，可能是主力提前知道了什么\n"
    "- 严格按第2步的搜索路由顺序，不要跳过 get_market_wire 直接 web_search"
)

_TAG_CLEANUP_PATTERNS = [
    re.compile(r"</?tool_call>"),
    re.compile(r'\{"name":\s*"[^"]+",\s*"arguments":\s*\{[^}]*\}\}'),
]

_FUND_SOURCE_RE = re.compile(r"资金来源[:：]\s*([^\n•]+)")
_JUDGEMENT_RE = re.compile(r"判断[:：]\s*([^\n•]+)")

# api/database.py's IntradaySignalDB.fund_source/judgement columns are
# String(64); truncate defensively here regardless of the current column
# width so a verbose LLM response can never trip a DB length error.
_SHORT_FIELD_MAX_LENGTH = 64


@dataclass(frozen=True)
class CauseAttributionResult:
    cause_summary: str
    fund_source: str | None
    judgement: str | None
    llm_failed: bool


def _clean_output(output: str) -> str:
    for pattern in _TAG_CLEANUP_PATTERNS:
        output = pattern.sub("", output)
    return output.strip()


def _truncate(value: str) -> str:
    return value[:_SHORT_FIELD_MAX_LENGTH]


def _fallback_result(anomaly: BoardAnomaly) -> CauseAttributionResult:
    raw_text = (
        f"【异动】{anomaly.board_name} Case {anomaly.anomaly_case}\n"
        f"涨跌幅 {anomaly.change_pct:.2f}%，净流入 {anomaly.net_inflow:.2f} 亿（归因生成失败，仅展示原始异动数据）"
    )
    return CauseAttributionResult(cause_summary=raw_text, fund_source=None, judgement=None, llm_failed=True)


async def analyze_cause(anomaly: BoardAnomaly, trade_date: str, config: Dict[str, Any]) -> CauseAttributionResult:
    """Run the cause-attribution agent for one anomaly. Never raises."""
    try:
        model = build_intraday_agent_model(config)
    except Exception as exc:
        logger.warning("[intraday] failed to build agent model: %s", exc)
        return _fallback_result(anomaly)

    agent = Agent(
        name="cause_analyst",
        instructions=_CAUSE_ANALYST_INSTRUCTIONS,
        model=model,
        tools=INTRADAY_CAUSE_TOOLS,
    )

    context = (
        f"以下是刚检测到的概念板块异动（交易日 {trade_date}），请按思维链路追因分析：\n\n"
        f"板块：{anomaly.board_name}\n"
        f"异动类型：Case {anomaly.anomaly_case}\n"
        f"涨跌幅：{anomaly.change_pct:.2f}%\n"
        f"净流入：{anomaly.net_inflow:.2f} 亿元"
    )

    try:
        result = await asyncio.wait_for(
            Runner.run(agent, context, max_turns=_MAX_TURNS),
            timeout=_TIMEOUT_SECONDS,
        )
        output = _clean_output(result.final_output or "")
        if len(output) < _MIN_OUTPUT_LENGTH:
            logger.warning("[intraday] cause analysis returned empty/garbage output for %s", anomaly.board_name)
            return _fallback_result(anomaly)

        fund_source_match = _FUND_SOURCE_RE.search(output)
        judgement_match = _JUDGEMENT_RE.search(output)
        return CauseAttributionResult(
            cause_summary=output,
            fund_source=_truncate(fund_source_match.group(1).strip()) if fund_source_match else None,
            judgement=_truncate(judgement_match.group(1).strip()) if judgement_match else None,
            llm_failed=False,
        )
    except asyncio.TimeoutError:
        logger.warning("[intraday] cause analysis timed out (%ds) for %s", _TIMEOUT_SECONDS, anomaly.board_name)
        return _fallback_result(anomaly)
    except Exception as exc:
        logger.warning("[intraday] cause analysis failed for %s: %s", anomaly.board_name, exc)
        return _fallback_result(anomaly)
