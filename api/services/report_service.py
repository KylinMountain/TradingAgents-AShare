"""Report service for database operations."""

import json
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.database import ReportDB


# ─── Structured extraction schemas ───────────────────────────────────────────

class RiskItemSchema(BaseModel):
    name: str = Field(..., description="风险名称，15字以内")
    level: Literal["high", "medium", "low"] = Field(..., description="风险等级")
    description: str = Field("", description="一句话说明，30字以内")


class KeyMetricSchema(BaseModel):
    name: str = Field(..., description="指标名称，如 PE、ROE、营收增速")
    value: str = Field(..., description="指标值，包含单位，如 28.5x、15.2%")
    status: Literal["good", "neutral", "bad"] = Field("neutral", description="优劣判断")


class StructuredReport(BaseModel):
    decision: str = Field("HOLD", description="交易决策关键词：BUY/SELL/HOLD/增持/减持/持有")
    confidence: Optional[int] = Field(None, description="整体置信度 0-100")
    target_price: Optional[float] = Field(None, description="目标价（数字，无单位）")
    stop_loss_price: Optional[float] = Field(None, description="止损价（数字，无单位）")
    risks: List[RiskItemSchema] = Field(default_factory=list, description="主要风险，最多5条")
    key_metrics: List[KeyMetricSchema] = Field(default_factory=list, description="关键指标，最多6条")


def extract_structured_data(
    final_trade_decision: str,
    fundamentals_report: str = "",
    config: Optional[Dict[str, Any]] = None,
) -> Optional[StructuredReport]:
    """Use LLM structured output to extract key data from report text."""
    if not final_trade_decision:
        return None
    if config is None:
        from tradingagents.default_config import DEFAULT_CONFIG
        config = DEFAULT_CONFIG

    try:
        from langchain_core.messages import HumanMessage
        from tradingagents.llm_clients import create_llm_client

        client = create_llm_client(
            provider=config.get("llm_provider", "openai"),
            model=config.get("quick_think_llm", "gpt-4o-mini"),
            base_url=config.get("backend_url"),
            api_key=config.get("api_key"),
        )
        llm = client.get_llm()
        structured_llm = llm.with_structured_output(StructuredReport)

        prompt = (
            "请从以下投资分析报告中提取结构化信息。\n\n"
            f"【最终交易决策】\n{final_trade_decision[:3000]}\n\n"
            f"【基本面报告摘要】\n{fundamentals_report[:1000]}\n\n"
            "提取要求：\n"
            "1. decision：决策方向关键词（BUY/SELL/HOLD 或 增持/减持/持有）\n"
            "2. confidence：整体置信度（0-100整数），若文中未明确给出则根据语气判断\n"
            "3. target_price / stop_loss_price：纯数字，若未提及则为 null\n"
            "4. risks：最多5条主要风险，每条包含名称（15字内）、等级（high/medium/low）、一句话说明\n"
            "5. key_metrics：最多6条关键财务/估值指标，每条包含名称、值（含单位）、优劣（good/neutral/bad）"
        )

        result = structured_llm.invoke([HumanMessage(content=prompt)])
        # 置信度范围校验
        if result.confidence is not None and not (0 <= result.confidence <= 100):
            result.confidence = None
        return result
    except Exception as e:
        print(f"[report_service] LLM structured extraction failed: {e}")
        return None


# ─── Fallback regex extraction (used when LLM extraction unavailable) ─────────

def _extract_confidence_regex(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    for pattern in (r'置信度[:：]\s*(\d+)%', r'confidence[:：]\s*(\d+)%'):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            v = int(m.group(1))
            return v if 0 <= v <= 100 else None
    return None


def _extract_price_regex(text: Optional[str], price_type: str = "target") -> Optional[float]:
    if not text:
        return None
    if price_type == "target":
        patterns = [
            r'目标价[:：]\s*[¥$]?\s*(\d+\.?\d*)',
            r'目标价格[:：]\s*[¥$]?\s*(\d+\.?\d*)',
            r'target[:：]\s*[¥$]?\s*(\d+\.?\d*)',
        ]
    else:
        patterns = [
            r'止损价[:：]\s*[¥$]?\s*(\d+\.?\d*)',
            r'止损价格[:：]\s*[¥$]?\s*(\d+\.?\d*)',
            r'stop[-\s_]?loss[:：]\s*[¥$]?\s*(\d+\.?\d*)',
        ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return None


def _extract_verdict(text: Optional[str]) -> Optional[Dict[str, str]]:
    if not text:
        return None
    match = re.search(r"<!--\s*VERDICT:\s*(\{.*?\})\s*-->", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except Exception:
        return None
    direction = str(payload.get("direction") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    if not direction:
        return None
    return {"direction": direction, "reason": reason}


def resolve_report_fields(
    result_data: Optional[Dict[str, Any]] = None,
    confidence_override: Optional[int] = None,
    target_price_override: Optional[float] = None,
    stop_loss_override: Optional[float] = None,
) -> Dict[str, Any]:
    """Resolve the final structured fields once for both SSE payloads and DB writes."""
    market_report = sentiment_report = news_report = None
    fundamentals_report = investment_plan = trader_investment_plan = None
    final_trade_decision = None

    if result_data:
        market_report = result_data.get("market_report")
        sentiment_report = result_data.get("sentiment_report")
        news_report = result_data.get("news_report")
        fundamentals_report = result_data.get("fundamentals_report")
        investment_plan = result_data.get("investment_plan")
        trader_investment_plan = result_data.get("trader_investment_plan")
        final_trade_decision = result_data.get("final_trade_decision")

    verdict = _extract_verdict(final_trade_decision)
    direction = verdict["direction"] if verdict else None

    confidence = confidence_override if confidence_override is not None else _extract_confidence_regex(final_trade_decision)

    target_price = target_price_override if target_price_override is not None else _extract_price_regex(final_trade_decision, "target")
    if target_price is None:
        target_price = _extract_price_regex(trader_investment_plan, "target")

    stop_loss_price = stop_loss_override if stop_loss_override is not None else _extract_price_regex(final_trade_decision, "stop_loss")
    if stop_loss_price is None:
        stop_loss_price = _extract_price_regex(trader_investment_plan, "stop_loss")

    return {
        "market_report": market_report,
        "sentiment_report": sentiment_report,
        "news_report": news_report,
        "fundamentals_report": fundamentals_report,
        "investment_plan": investment_plan,
        "trader_investment_plan": trader_investment_plan,
        "final_trade_decision": final_trade_decision,
        "direction": direction,
        "confidence": confidence,
        "target_price": target_price,
        "stop_loss_price": stop_loss_price,
    }


# ─── CRUD ────────────────────────────────────────────────────────────────────

def create_report(
    db: Session,
    symbol: str,
    trade_date: str,
    decision: Optional[str] = None,
    result_data: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    risk_items: Optional[List[dict]] = None,
    key_metrics: Optional[List[dict]] = None,
    confidence_override: Optional[int] = None,
    target_price_override: Optional[float] = None,
    stop_loss_override: Optional[float] = None,
) -> ReportDB:
    """Create a new report."""
    report_id = str(uuid4())
    resolved = resolve_report_fields(
        result_data=result_data,
        confidence_override=confidence_override,
        target_price_override=target_price_override,
        stop_loss_override=stop_loss_override,
    )

    now = datetime.now(timezone.utc)
    db_report = ReportDB(
        id=report_id,
        user_id=user_id,
        symbol=symbol,
        trade_date=trade_date,
        decision=decision,
        direction=resolved["direction"],
        confidence=resolved["confidence"],
        target_price=resolved["target_price"],
        stop_loss_price=resolved["stop_loss_price"],
        result_data=result_data,
        risk_items=risk_items,
        key_metrics=key_metrics,
        market_report=resolved["market_report"],
        sentiment_report=resolved["sentiment_report"],
        news_report=resolved["news_report"],
        fundamentals_report=resolved["fundamentals_report"],
        investment_plan=resolved["investment_plan"],
        trader_investment_plan=resolved["trader_investment_plan"],
        final_trade_decision=resolved["final_trade_decision"],
        created_at=now,
        updated_at=now,
    )

    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def get_report(db: Session, report_id: str, user_id: Optional[str] = None) -> Optional[ReportDB]:
    query = db.query(ReportDB).filter(ReportDB.id == report_id)
    if user_id:
        query = query.filter(ReportDB.user_id == user_id)
    return query.first()


def get_reports_by_user(
    db: Session,
    user_id: Optional[str] = None,
    symbol: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[ReportDB]:
    query = db.query(ReportDB)
    if user_id:
        query = query.filter(ReportDB.user_id == user_id)
    if symbol:
        query = query.filter(ReportDB.symbol == symbol)
    return query.order_by(ReportDB.created_at.desc()).offset(skip).limit(limit).all()


def count_reports(
    db: Session,
    user_id: Optional[str] = None,
    symbol: Optional[str] = None,
) -> int:
    query = db.query(func.count(ReportDB.id))
    if user_id:
        query = query.filter(ReportDB.user_id == user_id)
    if symbol:
        query = query.filter(ReportDB.symbol == symbol)
    return query.scalar() or 0


def delete_report(db: Session, report_id: str, user_id: Optional[str] = None) -> bool:
    query = db.query(ReportDB).filter(ReportDB.id == report_id)
    if user_id:
        query = query.filter(ReportDB.user_id == user_id)
    report = query.first()
    if report:
        db.delete(report)
        db.commit()
        return True
    return False
