"""Email report rendering and delivery service.

Renders analysis reports as HTML emails and sends them via SMTP,
reusing the same mail environment variables as auth_service.
"""
from __future__ import annotations

import asyncio
import html
import logging
import os
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

_SECTION_TITLES = [
    ("market_report", "市场分析"),
    ("sentiment_report", "舆情分析"),
    ("news_report", "新闻分析"),
    ("fundamentals_report", "基本面分析"),
    ("macro_report", "宏观分析"),
    ("smart_money_report", "主力资金分析"),
    ("game_theory_report", "博弈分析"),
]


def render_report_html(report: "ReportDB") -> str:
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

    # --- analysis sections ---
    for attr, title in _SECTION_TITLES:
        content = getattr(report, attr, None)
        if content is None:
            continue
        escaped = _escape(content).replace("\n", "<br>")
        parts.append('<tr><td style="padding:12px 24px;">')
        parts.append(f'<h3 style="font-size:14px;margin:0 0 8px;color:#1e3a5f;">{title}</h3>')
        parts.append(f'<div style="font-size:13px;color:#374151;line-height:1.6;">{escaped}</div>')
        parts.append('</td></tr>')

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

    # --- footer ---
    parts.append('<tr><td style="padding:16px 24px;border-top:1px solid #e5e7eb;text-align:center;">')
    parts.append('<p style="margin:0;font-size:11px;color:#9ca3af;">本报告由 TradingAgents 系统自动生成，仅供参考，不构成投资建议。</p>')
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

    html_body = render_report_html(report)
    symbol = report.symbol or ""
    trade_date = report.trade_date or ""

    msg = EmailMessage()
    msg["Subject"] = f"TradingAgents 投研报告 - {symbol} ({trade_date})"
    msg["From"] = smtp_from
    msg["To"] = user.email

    # text/plain fallback
    plain = f"TradingAgents 投研报告\n{symbol} {trade_date}\n决策: {report.decision or '-'}\n方向: {report.direction or '-'}\n置信度: {report.confidence or '-'}%\n\n请使用支持 HTML 的邮件客户端查看完整报告。"
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
