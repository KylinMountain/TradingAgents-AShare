from __future__ import annotations

import re
from datetime import datetime, timedelta, time
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from tradingagents.dataflows.trade_calendar import (
    CN_TZ,
    cn_market_phase,
    cn_today_str,
    is_cn_symbol,
    is_cn_trading_day,
    previous_cn_trading_day,
)

US_TZ = ZoneInfo("America/New_York")

USER_CONTEXT_KEYS = (
    "objective",
    "risk_profile",
    "investment_horizon",
    "cash_available",
    "current_position",
    "current_position_pct",
    "average_cost",
    "max_loss_pct",
    "constraints",
    "user_notes",
)


def infer_instrument_context(symbol: str) -> dict[str, Any]:
    normalized = (symbol or "").strip().upper()
    if is_cn_symbol(normalized):
        exchange = _infer_cn_exchange(normalized)
        return {
            "symbol": normalized,
            "security_name": normalized,
            "market_country": "CN",
            "exchange": exchange,
            "currency": "CNY",
            "asset_type": "equity",
        }

    if re.fullmatch(r"[A-Z]{1,6}(?:\.[A-Z]{1,4})?", normalized):
        exchange = normalized.split(".", 1)[1] if "." in normalized else "US"
        return {
            "symbol": normalized,
            "security_name": normalized,
            "market_country": "US",
            "exchange": exchange,
            "currency": "USD",
            "asset_type": "equity",
        }

    return {
        "symbol": normalized,
        "security_name": normalized,
        "market_country": "UNKNOWN",
        "exchange": "UNKNOWN",
        "currency": "UNKNOWN",
        "asset_type": "unknown",
    }


def build_market_context(symbol: str, trade_date: str, now: datetime | None = None) -> dict[str, Any]:
    instrument_context = infer_instrument_context(symbol)
    market_country = instrument_context["market_country"]

    if market_country == "CN":
        context = _build_cn_market_context(trade_date, now)
    elif market_country == "US":
        context = _build_us_market_context(trade_date, now)
    else:
        context = {
            "trade_date": trade_date,
            "timezone": "UTC",
            "market_session": "unknown",
            "market_is_open": False,
            "analysis_mode": "historical",
            "data_as_of": trade_date,
            "session_note": "无法识别市场归属，未推断交易时段。",
        }

    context["market_country"] = market_country
    context["exchange"] = instrument_context["exchange"]
    return context


def normalize_user_context(raw: Mapping[str, Any] | None = None) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if not raw:
        return context

    for key in USER_CONTEXT_KEYS:
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        if key == "constraints":
            constraints = [str(item).strip() for item in value or [] if str(item).strip()]
            if constraints:
                context[key] = constraints
            continue
        context[key] = value

    return context


def summarize_instrument_context(context: Mapping[str, Any] | None) -> str:
    ctx = context or {}
    return "\n".join(
        [
            f"标的代码：{ctx.get('symbol', '—')}",
            f"市场归属：{ctx.get('market_country', '—')}",
            f"交易所：{ctx.get('exchange', '—')}",
            f"币种：{ctx.get('currency', '—')}",
            f"资产类型：{ctx.get('asset_type', '—')}",
        ]
    )


def summarize_market_context(context: Mapping[str, Any] | None) -> str:
    ctx = context or {}
    return "\n".join(
        [
            f"交易日期：{ctx.get('trade_date', '—')}",
            f"时区：{ctx.get('timezone', '—')}",
            f"市场状态：{ctx.get('market_session', '—')}",
            f"当前是否开市：{'是' if ctx.get('market_is_open') else '否'}",
            f"分析模式：{ctx.get('analysis_mode', '—')}",
            f"数据截至：{ctx.get('data_as_of', '—')}",
            f"说明：{ctx.get('session_note', '—')}",
        ]
    )


def summarize_user_context(context: Mapping[str, Any] | None) -> str:
    ctx = context or {}
    if not ctx:
        return "未提供用户持仓或风险约束。"

    lines = [
        f"目标动作：{ctx.get('objective', '未说明')}",
        f"风险偏好：{ctx.get('risk_profile', '未说明')}",
        f"持有周期：{ctx.get('investment_horizon', '未说明')}",
        f"可用资金：{ctx.get('cash_available', '未说明')}",
        f"当前持仓：{ctx.get('current_position', '未说明')}",
        f"当前仓位占比：{ctx.get('current_position_pct', '未说明')}",
        f"持仓成本：{ctx.get('average_cost', '未说明')}",
        f"最大容忍亏损：{ctx.get('max_loss_pct', '未说明')}",
    ]
    constraints = ctx.get("constraints") or []
    if constraints:
        lines.append(f"硬约束：{'; '.join(str(item) for item in constraints)}")
    if ctx.get("user_notes"):
        lines.append(f"用户补充：{ctx['user_notes']}")
    return "\n".join(lines)


def build_agent_context_view(state: Mapping[str, Any], role: str) -> dict[str, str]:
    role_key = role.lower()
    instrument_context = state.get("instrument_context", {})
    market_context = state.get("market_context", {})
    user_context = state.get("user_context", {})

    user_summary = summarize_user_context(user_context)
    if role_key in {"analyst", "research"} and user_context:
        user_summary = "\n".join(
            [
                f"目标动作：{user_context.get('objective', '未说明')}",
                f"风险偏好：{user_context.get('risk_profile', '未说明')}",
                f"持有周期：{user_context.get('investment_horizon', '未说明')}",
            ]
        )

    return {
        "instrument_context_summary": summarize_instrument_context(instrument_context),
        "market_context_summary": summarize_market_context(market_context),
        "user_context_summary": user_summary,
    }


def _build_cn_market_context(trade_date: str, now: datetime | None = None) -> dict[str, Any]:
    now_dt = (now or datetime.now(CN_TZ)).astimezone(CN_TZ)
    today = now_dt.date().strftime("%Y-%m-%d")
    is_trade_day = is_cn_trading_day(trade_date)

    if trade_date == today:
        market_session = cn_market_phase(now_dt)
    elif trade_date < today and is_trade_day:
        market_session = "post_close"
    elif trade_date > today and is_trade_day:
        market_session = "pre_open"
    else:
        market_session = "closed"

    analysis_mode = _determine_cn_analysis_mode(trade_date, today, market_session)
    return {
        "trade_date": trade_date,
        "timezone": "Asia/Shanghai",
        "market_session": market_session,
        "market_is_open": trade_date == today and market_session == "in_session",
        "analysis_mode": analysis_mode,
        "data_as_of": _cn_data_as_of(trade_date, today, market_session),
        "session_note": _cn_session_note(trade_date, today, market_session, is_trade_day),
    }


def _build_us_market_context(trade_date: str, now: datetime | None = None) -> dict[str, Any]:
    now_dt = (now or datetime.now(US_TZ)).astimezone(US_TZ)
    today = now_dt.date().strftime("%Y-%m-%d")
    is_trade_day = _is_us_trading_day(trade_date)

    if trade_date == today:
        market_session = _us_market_phase(now_dt) if is_trade_day else "closed"
    elif trade_date < today and is_trade_day:
        market_session = "post_close"
    elif trade_date > today and is_trade_day:
        market_session = "pre_open"
    else:
        market_session = "closed"

    analysis_mode = _determine_us_analysis_mode(trade_date, today, market_session)
    return {
        "trade_date": trade_date,
        "timezone": "America/New_York",
        "market_session": market_session,
        "market_is_open": trade_date == today and market_session == "in_session",
        "analysis_mode": analysis_mode,
        "data_as_of": trade_date if trade_date <= today else today,
        "session_note": _us_session_note(trade_date, today, market_session, is_trade_day),
    }


def _infer_cn_exchange(symbol: str) -> str:
    parts = symbol.split(".", 1)
    if len(parts) == 2:
        suffix = parts[1]
        if suffix == "SS":
            return "SH"
        return suffix

    code = parts[0]
    if code.startswith(("4", "8")):
        return "BJ"
    if code.startswith(("5", "6", "9")):
        return "SH"
    return "SZ"


def _determine_cn_analysis_mode(trade_date: str, today: str, market_session: str) -> str:
    if trade_date == today:
        if market_session == "pre_open":
            return "pre_market"
        if market_session in {"in_session", "lunch_break"}:
            return "intraday"
        if market_session == "post_close":
            return "post_market"
        return "closed"

    if trade_date == previous_cn_trading_day(today):
        return "t_plus_1"
    if trade_date > today:
        return "forward_look"
    return "historical"


def _determine_us_analysis_mode(trade_date: str, today: str, market_session: str) -> str:
    if trade_date == today:
        if market_session == "pre_open":
            return "pre_market"
        if market_session in {"in_session", "lunch_break"}:
            return "intraday"
        if market_session == "post_close":
            return "post_market"
        return "closed"

    if trade_date == _previous_us_trading_day(today):
        return "t_plus_1"
    if trade_date > today:
        return "forward_look"
    return "historical"


def _cn_data_as_of(trade_date: str, today: str, market_session: str) -> str:
    if trade_date > today:
        return today
    if trade_date == today and market_session in {"pre_open", "in_session", "lunch_break"}:
        return today
    return trade_date


def _cn_session_note(trade_date: str, today: str, market_session: str, is_trade_day: bool) -> str:
    if not is_trade_day:
        return "请求日期为 A 股非交易日。"
    if trade_date > today:
        return "请求日期晚于当前日期，按最新可用市场状态推断。"
    if trade_date < today:
        return "请求日期为历史 A 股交易日，市场已收盘。"
    if market_session == "pre_open":
        return "A 股盘前时段。"
    if market_session == "lunch_break":
        return "A 股午间休市，盘中数据可能仍在变化。"
    if market_session == "in_session":
        return "A 股当前处于交易时段。"
    return "A 股已收盘，部分数据源可能仍在更新。"


def _is_us_trading_day(date_str: str) -> bool:
    return datetime.strptime(date_str, "%Y-%m-%d").weekday() < 5


def _previous_us_trading_day(date_str: str) -> str:
    current = datetime.strptime(date_str, "%Y-%m-%d")
    while True:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            return current.strftime("%Y-%m-%d")


def _us_market_phase(now_dt: datetime) -> str:
    local = now_dt.astimezone(US_TZ)
    current_time = local.time()
    if current_time < time(9, 30):
        return "pre_open"
    if time(9, 30) <= current_time < time(16, 0):
        return "in_session"
    return "post_close"


def _us_session_note(trade_date: str, today: str, market_session: str, is_trade_day: bool) -> str:
    if not is_trade_day:
        return "请求日期为美股非交易日。"
    if trade_date > today:
        return "请求日期晚于当前日期，按最新可用市场状态推断。"
    if trade_date < today:
        return "请求日期为历史美股交易日，市场已收盘。"
    if market_session == "pre_open":
        return "美股当前处于盘前时段。"
    if market_session == "in_session":
        return "美股当前处于交易时段。"
    return "美股已收盘。"
