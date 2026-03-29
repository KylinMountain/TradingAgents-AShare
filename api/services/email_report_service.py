"""Email report rendering and delivery service.

Renders analysis reports as HTML emails and sends them via SMTP,
reusing the same mail environment variables as auth_service.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
import smtplib
from email.message import EmailMessage
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from api.database import ReportDB, UserDB

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_env_alias(keys: list[str], default: str = "") -> str:
    """Return the first non-None env var from *keys*, else *default*."""
    for k in keys:
        v = os.getenv(k)
        if v is not None:
            return v
    return default


def _escape(text: str) -> str:
    """HTML-escape user-supplied text."""
    return html.escape(str(text))


def _infer_frontend_url() -> str:
    """Infer frontend URL from FRONTEND_URL or CORS_ALLOW_ORIGINS.

    Priority: FRONTEND_URL env > first non-localhost CORS origin > first CORS origin > "".
    """
    explicit = os.getenv("FRONTEND_URL", "").strip()
    if explicit:
        return explicit
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        return ""
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    # Prefer non-localhost origin (production URL)
    for o in origins:
        if "localhost" not in o and "127.0.0.1" not in o:
            return o
    return origins[0] if origins else ""


_VERDICT_RE = re.compile(r"<!--\s*VERDICT:\s*(\{[^>]+\})\s*-->")
_DIRECTION_ALIAS = {
    "BULLISH": "看多",
    "BEARISH": "看空",
    "NEUTRAL": "中性",
    "CAUTIOUS": "谨慎",
}


def _extract_verdict(text: str) -> Optional[dict]:
    """Extract structured verdict from agent report HTML comment.

    Returns {"direction": "看多", "reason": "..."} or None.
    """
    m = _VERDICT_RE.search(text)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(1))
        direction = parsed.get("direction", "")
        reason = parsed.get("reason", "")
        if not direction or not reason:
            return None
        direction = _DIRECTION_ALIAS.get(direction.upper(), direction)
        return {"direction": direction, "reason": reason.strip()[:42]}
    except (json.JSONDecodeError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

_DIRECTION_COLOR = {
    "看多": "#16a34a",
    "多": "#16a34a",
    "看空": "#dc2626",
    "空": "#dc2626",
    "中性": "#9ca3af",
    "谨慎": "#f59e0b",
}

_RISK_LEVEL_COLORS = {
    "high": "#dc2626",
    "medium": "#f59e0b",
    "low": "#16a34a",
}

_KEY_METRIC_STATUS_COLORS = {
    "good": "#16a34a",
    "neutral": "#6b7280",
    "bad": "#dc2626",
}

_AGENT_SECTIONS = [
    ("market_report", "市场分析"),
    ("sentiment_report", "舆情分析"),
    ("news_report", "新闻分析"),
    ("fundamentals_report", "基本面分析"),
    ("macro_report", "宏观分析"),
    ("smart_money_report", "主力资金分析"),
    ("game_theory_report", "博弈分析"),
]


_GITHUB_URL = "https://github.com/KylinMountain/TradingAgents-AShare"


def render_report_html(report: "ReportDB", frontend_url: str = "") -> str:
    """Render a *ReportDB* instance as an HTML email string with inline CSS."""

    symbol = _escape(report.symbol or "")
    trade_date = _escape(report.trade_date or "")
    decision = _escape(report.decision or "-")
    direction = report.direction or ""
    direction_color = _DIRECTION_COLOR.get(direction, "#6b7280")
    confidence = report.confidence if report.confidence is not None else "-"
    target_price = report.target_price if report.target_price is not None else "-"
    stop_loss = report.stop_loss_price if report.stop_loss_price is not None else "-"

    # --- header ---
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="zh"><head><meta charset="utf-8"></head>',
        '<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">',
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">',
        '<tr><td align="center" style="padding:24px 0;">',
        '<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">',
        # header bar
        '<tr><td style="background:#1e3a5f;padding:20px 24px;">',
        f'<h1 style="margin:0;color:#ffffff;font-size:18px;">TradingAgents 投研报告</h1>',
        f'<p style="margin:4px 0 0;color:#93c5fd;font-size:14px;">{symbol} | {trade_date}</p>',
        '</td></tr>',
    ]

    # --- decision summary ---
    parts.append('<tr><td style="padding:20px 24px;">')
    parts.append('<h2 style="font-size:16px;margin:0 0 12px;color:#1e3a5f;">决策摘要</h2>')
    parts.append('<table width="100%" cellpadding="6" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:4px;">')
    summary_rows = [
        ("决策", decision),
        ("方向", f'<span style="color:{direction_color};font-weight:bold;">{_escape(direction)}</span>'),
        ("置信度", f"{confidence}%"if confidence != "-" else "-"),
        ("目标价", str(target_price)),
        ("止损价", str(stop_loss)),
    ]
    for i, (label, value) in enumerate(summary_rows):
        bg = "#f9fafb" if i % 2 == 0 else "#ffffff"
        parts.append(f'<tr style="background:{bg};"><td style="width:30%;color:#6b7280;font-size:13px;">{label}</td><td style="font-size:13px;">{value}</td></tr>')
    parts.append('</table></td></tr>')

    # --- agent verdicts (one-line summaries, not full reports) ---
    verdicts: list[tuple[str, dict]] = []
    for attr, title in _AGENT_SECTIONS:
        content = getattr(report, attr, None)
        if content is None:
            continue
        verdict = _extract_verdict(content)
        if verdict:
            verdicts.append((title, verdict))

    if verdicts:
        parts.append('<tr><td style="padding:12px 24px;">')
        parts.append('<h2 style="font-size:16px;margin:0 0 12px;color:#1e3a5f;">各方观点</h2>')
        parts.append('<table width="100%" cellpadding="8" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:4px;">')
        for i, (title, v) in enumerate(verdicts):
            bg = "#f9fafb" if i % 2 == 0 else "#ffffff"
            d_color = _DIRECTION_COLOR.get(v["direction"], "#6b7280")
            parts.append(
                f'<tr style="background:{bg};">'
                f'<td style="width:25%;font-size:13px;color:#6b7280;">{title}</td>'
                f'<td style="width:15%;font-size:13px;font-weight:bold;color:{d_color};">{_escape(v["direction"])}</td>'
                f'<td style="font-size:13px;color:#374151;">{_escape(v["reason"])}</td>'
                f'</tr>'
            )
        parts.append('</table></td></tr>')

    # --- key metrics ---
    key_metrics: Optional[List[dict]] = getattr(report, "key_metrics", None)
    if key_metrics:
        parts.append('<tr><td style="padding:12px 24px;">')
        parts.append('<h2 style="font-size:16px;margin:0 0 12px;color:#1e3a5f;">关键指标</h2>')
        parts.append('<table width="100%" cellpadding="6" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:4px;font-size:13px;">')
        parts.append('<tr style="background:#f1f5f9;"><th style="text-align:left;">指标</th><th style="text-align:left;">数值</th><th style="text-align:left;">状态</th></tr>')
        status_labels = {"good": "良好", "neutral": "中性", "bad": "不佳"}
        for item in key_metrics:
            name = _escape(item.get("name", ""))
            value = _escape(item.get("value", ""))
            status = item.get("status", "")
            s_color = _KEY_METRIC_STATUS_COLORS.get(status, "#6b7280")
            s_label = status_labels.get(status, status)
            parts.append(f'<tr><td>{name}</td><td>{value}</td><td style="color:{s_color};font-weight:bold;">{_escape(s_label)}</td></tr>')
        parts.append('</table></td></tr>')

    # --- risk items ---
    risk_items: Optional[List[dict]] = getattr(report, "risk_items", None)
    if risk_items:
        parts.append('<tr><td style="padding:12px 24px;">')
        parts.append('<h3 style="font-size:14px;margin:0 0 8px;color:#1e3a5f;">风险提示</h3>')
        parts.append('<table width="100%" cellpadding="6" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:4px;font-size:13px;">')
        parts.append('<tr style="background:#f1f5f9;"><th style="text-align:left;">风险</th><th style="text-align:left;">等级</th><th style="text-align:left;">说明</th></tr>')
        for item in risk_items:
            name = _escape(item.get("name", ""))
            level = item.get("level", "")
            level_color = _RISK_LEVEL_COLORS.get(level, "#6b7280")
            desc = _escape(item.get("description", ""))
            parts.append(f'<tr><td>{name}</td><td style="color:{level_color};font-weight:bold;">{_escape(level)}</td><td>{desc}</td></tr>')
        parts.append('</table></td></tr>')

    # --- final trade decision ---
    ftd = getattr(report, "final_trade_decision", None)
    if ftd:
        escaped_ftd = _escape(ftd).replace("\n", "<br>")
        parts.append('<tr><td style="padding:12px 24px;">')
        parts.append('<h3 style="font-size:14px;margin:0 0 8px;color:#1e3a5f;">最终交易决策</h3>')
        parts.append(f'<div style="font-size:13px;color:#374151;line-height:1.6;background:#f9fafb;padding:12px;border-radius:4px;">{escaped_ftd}</div>')
        parts.append('</td></tr>')

    # --- view full report button ---
    if frontend_url:
        report_url = f"{frontend_url.rstrip('/')}/reports?report={report.id}"
        parts.append('<tr><td style="padding:20px 24px;" align="center">')
        parts.append(
            f'<a href="{_escape(report_url)}" target="_blank" style="'
            'display:inline-block;background:#1e3a5f;color:#ffffff;'
            'font-size:14px;font-weight:bold;padding:10px 28px;'
            'border-radius:6px;text-decoration:none;">'
            '查看完整报告</a>'
        )
        parts.append('</td></tr>')

    # --- footer ---
    parts.append('<tr><td style="padding:16px 24px;border-top:1px solid #e5e7eb;text-align:center;">')
    parts.append('<p style="margin:0;font-size:11px;color:#9ca3af;">本报告由 TradingAgents 系统自动生成，仅供参考，不构成投资建议。</p>')
    parts.append(
        f'<p style="margin:6px 0 0;font-size:11px;color:#9ca3af;">'
        f'<a href="{_GITHUB_URL}" style="color:#3b82f6;text-decoration:none;">TradingAgents-AShare</a>'
        f' — A 股多智能体智能投研系统，15 名 AI Agent 协作分析，全流程可视化。'
        f'</p>'
    )
    parts.append(
        f'<p style="margin:6px 0 0;font-size:11px;color:#9ca3af;">'
        f'觉得有帮助？给项目点个 '
        f'<a href="{_GITHUB_URL}" style="color:#3b82f6;text-decoration:none;">⭐ Star</a>'
        f' 或 '
        f'<a href="{_GITHUB_URL}/sponsors" style="color:#3b82f6;text-decoration:none;">赞助支持</a>'
        f' 让更多人发现它。'
        f'</p>'
    )
    parts.append('</td></tr>')
    parts.append('</table></td></tr></table></body></html>')

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# SMTP sending
# ---------------------------------------------------------------------------

def send_report_email(user: "UserDB", report: "ReportDB") -> bool:
    """Send the rendered report email via SMTP.

    Returns True on success, False on failure.  Never raises.
    """
    smtp_host = _get_env_alias(["MAIL_HOST", "MAIL_SERVER", "SMTP_HOST"]).strip()
    if not smtp_host:
        logger.info("[email_report] SMTP not configured, skipping send")
        return False

    smtp_port = int(_get_env_alias(["MAIL_PORT", "SMTP_PORT"]) or "587")
    smtp_user = _get_env_alias(["MAIL_USER", "MAIL_USERNAME", "SMTP_USER"]).strip()
    smtp_password = _get_env_alias(["MAIL_PASS", "MAIL_PASSWORD", "SMTP_PASSWORD"]).strip()
    smtp_from = _get_env_alias(["MAIL_FROM", "SMTP_FROM"], smtp_user or "noreply@example.com").strip()

    smtp_starttls_str = _get_env_alias(["MAIL_STARTTLS", "SMTP_TLS"], "1").strip().lower()
    smtp_starttls = smtp_starttls_str not in ("0", "false", "off", "no")

    smtp_ssl_tls_str = _get_env_alias(["MAIL_SSL", "MAIL_SSL_TLS"], "0").strip().lower()
    smtp_ssl_tls = smtp_ssl_tls_str in ("1", "true", "on", "yes")

    frontend_url = _infer_frontend_url()
    html_body = render_report_html(report, frontend_url=frontend_url)
    symbol = report.symbol or ""
    trade_date = report.trade_date or ""

    report_link = ""
    if frontend_url:
        report_link = f"\n\n查看完整报告: {frontend_url.rstrip('/')}/reports?report={report.id}"

    msg = EmailMessage()
    msg["Subject"] = f"TradingAgents 投研报告 - {symbol} ({trade_date})"
    msg["From"] = smtp_from
    msg["To"] = user.email

    # text/plain fallback
    plain = f"TradingAgents 投研报告\n{symbol} {trade_date}\n决策: {report.decision or '-'}\n方向: {report.direction or '-'}\n置信度: {report.confidence or '-'}%{report_link}\n\n请使用支持 HTML 的邮件客户端查看完整报告。"
    msg.set_content(plain)
    msg.add_alternative(html_body, subtype="html")

    try:
        logger.info(f"[email_report] sending to {user.email} via {smtp_host}:{smtp_port}")
        smtp_cls = smtplib.SMTP_SSL if smtp_ssl_tls else smtplib.SMTP
        with smtp_cls(smtp_host, smtp_port, timeout=20) as server:
            if smtp_starttls and not smtp_ssl_tls:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info(f"[email_report] sent OK to {user.email}")
        return True
    except Exception as e:
        logger.error(f"[email_report] failed to send to {user.email}: {e}")
        return False


# ---------------------------------------------------------------------------
# Async wrapper with retry
# ---------------------------------------------------------------------------

async def send_report_email_with_retry(user: "UserDB", report: "ReportDB") -> bool:
    """Send report email asynchronously, retrying once on failure after 180 s."""
    ok = await asyncio.to_thread(send_report_email, user, report)
    if ok:
        logger.info(f"[email_report] first attempt succeeded for {user.email}")
        return True

    logger.warning(f"[email_report] first attempt failed for {user.email}, retrying in 180s")
    await asyncio.sleep(180)
    ok = await asyncio.to_thread(send_report_email, user, report)
    if ok:
        logger.info(f"[email_report] retry succeeded for {user.email}")
    else:
        logger.error(f"[email_report] retry also failed for {user.email}")
    return ok
