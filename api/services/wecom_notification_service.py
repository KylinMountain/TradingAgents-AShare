from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from api.database import ReportDB

logger = logging.getLogger(__name__)


def _clip_text(text: str | None, limit: int = 720) -> str:
    if not text:
        return ""
    compact = " ".join(str(text).split()).strip()
    return compact[:limit]


def build_report_message(report: "ReportDB") -> str:
    lines = [
        "TradingAgents 定时分析完成",
        f"标的：{report.symbol}",
        f"交易日：{report.trade_date}",
    ]
    if getattr(report, "decision", None):
        lines.append(f"决策：{report.decision}")
    if getattr(report, "direction", None):
        lines.append(f"方向：{report.direction}")
    if getattr(report, "confidence", None) is not None:
        lines.append(f"置信度：{report.confidence}%")

    summary = (
        _clip_text(getattr(report, "final_trade_decision", None), 900)
        or _clip_text(getattr(report, "trader_investment_plan", None), 900)
        or _clip_text(getattr(report, "investment_plan", None), 900)
    )
    if summary:
        lines.append("")
        lines.append("摘要：")
        lines.append(summary)
    return "\n".join(lines)[:1800]


def build_test_message(content: str | None = None) -> str:
    custom = " ".join(str(content or "").split()).strip()
    message = custom or "TradingAgents Webhook Warmup\n这是一条企业微信机器人测试消息。"
    return message[:1800]


def send_message(content: str, webhook_url: str) -> bool:
    if not webhook_url:
        return False
    payload = {
        "msgtype": "text",
        "text": {"content": content},
    }
    url = webhook_url if webhook_url.startswith("http") else (
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + webhook_url
    )
    response = requests.post(
        url,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json;charset=utf-8"},
        timeout=10,
    )
    response.raise_for_status()
    try:
        body = response.json()
    except Exception:
        body = {}
    return int(body.get("errcode", 0)) == 0


async def send_report_message_with_retry(report: "ReportDB", webhook_url: str) -> bool:
    content = build_report_message(report)
    try:
        ok = await asyncio.to_thread(send_message, content, webhook_url)
        if ok:
            logger.info("[wecom] sent OK for %s", report.symbol)
            return True
    except Exception as exc:
        logger.warning("[wecom] first send failed for %s: %s", report.symbol, exc)

    await asyncio.sleep(15)
    try:
        ok = await asyncio.to_thread(send_message, content, webhook_url)
        if ok:
            logger.info("[wecom] retry sent OK for %s", report.symbol)
            return True
    except Exception as exc:
        logger.error("[wecom] retry failed for %s: %s", report.symbol, exc)
    return False
