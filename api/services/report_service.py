"""Report service for database operations."""

import json
import json_repair
import logging
import re

logger = logging.getLogger(__name__)
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Iterable, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, load_only

from api.database import ReportDB


REPORT_SUMMARY_COLUMNS = (
    ReportDB.id,
    ReportDB.user_id,
    ReportDB.symbol,
    ReportDB.trade_date,
    ReportDB.status,
    ReportDB.error,
    ReportDB.decision,
    ReportDB.direction,
    ReportDB.confidence,
    ReportDB.target_price,
    ReportDB.stop_loss_price,
    ReportDB.risk_items,
    ReportDB.key_metrics,
    ReportDB.analyst_traces,
    ReportDB.created_at,
    ReportDB.updated_at,
)

ACTIVE_REPORT_STATUSES = ("pending", "running")
STALE_REPORT_ERROR_MESSAGE = "分析任务已中断，请重新发起分析"


# ─── Structured extraction schemas ───────────────────────────────────────────

from pydantic import field_validator


class RiskItemSchema(BaseModel):
    name: str = Field(..., description="风险名称，15字以内")
    level: str = Field("medium", description="风险等级")
    description: str = Field("", description="一句话说明，30字以内")

    @field_validator("level", mode="before")
    @classmethod
    def _coerce_level(cls, v):
        if isinstance(v, str) and v.lower() in ("high", "medium", "low"):
            return v.lower()
        return "medium"


class KeyMetricSchema(BaseModel):
    name: str = Field(..., description="指标名称，如 PE、ROE、营收增速")
    value: str = Field(..., description="指标值，包含单位，如 28.5x、15.2%")
    status: str = Field("neutral", description="优劣判断")

    @field_validator("value", mode="before")
    @classmethod
    def _coerce_value(cls, v):
        # LLM 可能返回数字而非字符串
        return str(v) if not isinstance(v, str) else v

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v):
        if isinstance(v, str) and v.lower() in ("good", "neutral", "bad"):
            return v.lower()
        return "neutral"


class StructuredReport(BaseModel):
    decision: str = Field("HOLD", description="交易决策关键词：BUY/SELL/HOLD/增持/减持/持有")
    confidence: Optional[int] = Field(None, description="整体置信度 0-100")
    target_price: Optional[float] = Field(None, description="目标价（数字，无单位）")
    stop_loss_price: Optional[float] = Field(None, description="止损价（数字，无单位）")
    risks: List[RiskItemSchema] = Field(default_factory=list, description="主要风险，最多5条")
    key_metrics: List[KeyMetricSchema] = Field(default_factory=list, description="关键指标，最多6条")

    @field_validator("target_price", "stop_loss_price", mode="before")
    @classmethod
    def _coerce_price(cls, v):
        # LLM 可能返回数组 [34.0, 32.5] 而非单个数字，取第一个
        if isinstance(v, list):
            return v[0] if v else None
        return v


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

        prompt = (
            "请从以下投资分析报告中提取结构化信息，并以 JSON 格式返回。\n\n"
            f"【最终交易决策】\n{final_trade_decision[:3000]}\n\n"
            f"【基本面报告摘要】\n{fundamentals_report[:1000]}\n\n"
            "提取要求（请确保输出为有效的 JSON 对象，不要包裹在 markdown 代码块中）：\n"
            "1. decision：决策方向关键词（BUY/SELL/HOLD 或 增持/减持/持有）\n"
            "2. confidence：整体置信度（0-100整数），若文中未明确给出则根据语气判断\n"
            "3. target_price / stop_loss_price：纯数字，若未提及则为 null\n"
            "4. risks：最多5条主要风险，每条包含名称（15字内）、等级（high/medium/low）、一句话说明\n"
            "5. key_metrics：最多6条关键财务/估值指标，每条包含名称、值（含单位）、优劣（good/neutral/bad）"
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content if hasattr(response, "content") else str(response)
        parsed = json_repair.loads(raw)
        result = StructuredReport(**parsed)
        if result.confidence is not None and not (0 <= result.confidence <= 100):
            result.confidence = None
        return result
    except Exception as e:
        logger.warning(f"LLM structured extraction failed: {e}")
        if 'raw' in locals():
            logger.warning(f"Raw LLM output:\n{raw}")
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
        # Clean potential newlines or invisible characters common in LLM outputs
        raw_json = match.group(1).strip().replace('\n', ' ').replace('\r', ' ')
        payload = json.loads(raw_json)
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
    fundamentals_report = macro_report = smart_money_report = volume_price_report = game_theory_report = None
    investment_plan = trader_investment_plan = None
    final_trade_decision = None

    if result_data:
        market_report = result_data.get("market_report")
        sentiment_report = result_data.get("sentiment_report")
        news_report = result_data.get("news_report")
        fundamentals_report = result_data.get("fundamentals_report")
        macro_report = result_data.get("macro_report")
        smart_money_report = result_data.get("smart_money_report")
        volume_price_report = result_data.get("volume_price_report")
        game_theory_report = result_data.get("game_theory_report")
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
        "macro_report": macro_report,
        "smart_money_report": smart_money_report,
        "volume_price_report": volume_price_report,
        "game_theory_report": game_theory_report,
        "investment_plan": investment_plan,
        "trader_investment_plan": trader_investment_plan,
        "final_trade_decision": final_trade_decision,
        "direction": direction,
        "confidence": confidence,
        "target_price": target_price,
        "stop_loss_price": stop_loss_price,
    }


# ─── CRUD ────────────────────────────────────────────────────────────────────

def init_report(
    db: Session,
    report_id: str,
    symbol: str,
    trade_date: str,
    user_id: Optional[str] = None,
) -> ReportDB:
    """Create a pending report record when a job is submitted."""
    now = datetime.now(timezone.utc)
    db_report = ReportDB(
        id=report_id,
        user_id=user_id,
        symbol=symbol,
        trade_date=trade_date,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def update_report_partial(
    db: Session,
    report_id: str,
    status: Optional[str] = None,
    **fields: Any
) -> Optional[ReportDB]:
    """Update specific fields of an existing report (e.g., partial analyst reports)."""
    db_report = db.query(ReportDB).filter(ReportDB.id == report_id).first()
    if not db_report:
        return None
    
    if status:
        db_report.status = status
    
    for key, value in fields.items():
        if hasattr(db_report, key):
            setattr(db_report, key, value)
    
    db_report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_report)
    return db_report


def finalize_orphan_report(
    db: Session,
    report: ReportDB,
    *,
    error_message: str = STALE_REPORT_ERROR_MESSAGE,
) -> ReportDB:
    """Mark an orphaned pending/running report as failed."""
    if str(report.status or "") not in ACTIVE_REPORT_STATUSES:
        return report

    report.status = "failed"
    report.error = error_message
    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)
    return report


def recover_stale_active_reports(
    db: Session,
    *,
    active_job_ids: Optional[Iterable[str]] = None,
    error_message: str = STALE_REPORT_ERROR_MESSAGE,
) -> Dict[str, int]:
    """Recover stale pending/running reports left behind by interrupted jobs."""
    active_job_id_set = {str(job_id) for job_id in (active_job_ids or []) if str(job_id).strip()}
    rows = (
        db.query(ReportDB)
        .filter(ReportDB.status.in_(ACTIVE_REPORT_STATUSES))
        .all()
    )
    if not rows:
        return {"total": 0, "failed": 0}

    failed = 0
    changed = False
    now = datetime.now(timezone.utc)
    for row in rows:
        if str(row.id) in active_job_id_set:
            continue
        row.status = "failed"
        row.error = error_message
        row.updated_at = now
        changed = True
        failed += 1

    if changed:
        db.commit()

    return {
        "total": failed,
        "failed": failed,
    }


def mark_report_failed(
    db: Session,
    report_id: str,
    error_message: str
) -> Optional[ReportDB]:
    """Mark a report as failed with an error message."""
    return update_report_partial(db, report_id, status="failed", error=error_message)


def create_report(
    db: Session,
    symbol: str,
    trade_date: str,
    decision: Optional[str] = None,
    result_data: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    risk_items: Optional[List[dict]] = None,
    key_metrics: Optional[List[dict]] = None,
    analyst_traces: Optional[List[dict]] = None,
    confidence_override: Optional[int] = None,
    target_price_override: Optional[float] = None,
    stop_loss_override: Optional[float] = None,
    report_id: Optional[str] = None,  # If provided, update existing
) -> ReportDB:
    """Create or finalize a report."""
    resolved = resolve_report_fields(
        result_data=result_data,
        confidence_override=confidence_override,
        target_price_override=target_price_override,
        stop_loss_override=stop_loss_override,
    )

    now = datetime.now(timezone.utc)
    
    # Check if we should update an existing record (initialized via init_report)
    db_report = None
    if report_id:
        db_report = db.query(ReportDB).filter(ReportDB.id == report_id).first()

    if db_report:
        # Update existing
        db_report.status = "completed"
        db_report.decision = decision
        db_report.direction = resolved["direction"]
        db_report.confidence = resolved["confidence"]
        db_report.target_price = resolved["target_price"]
        db_report.stop_loss_price = resolved["stop_loss_price"]
        db_report.result_data = result_data
        db_report.risk_items = risk_items
        db_report.key_metrics = key_metrics
        db_report.analyst_traces = analyst_traces
        db_report.market_report = resolved["market_report"]
        db_report.sentiment_report = resolved["sentiment_report"]
        db_report.news_report = resolved["news_report"]
        db_report.fundamentals_report = resolved["fundamentals_report"]
        db_report.macro_report = resolved["macro_report"]
        db_report.smart_money_report = resolved["smart_money_report"]
        db_report.volume_price_report = resolved["volume_price_report"]
        db_report.game_theory_report = resolved["game_theory_report"]
        db_report.investment_plan = resolved["investment_plan"]
        db_report.trader_investment_plan = resolved["trader_investment_plan"]
        db_report.final_trade_decision = resolved["final_trade_decision"]
        db_report.updated_at = now
    else:
        # Create new
        db_report = ReportDB(
            id=report_id or str(uuid4()),
            user_id=user_id,
            symbol=symbol,
            trade_date=trade_date,
            status="completed",
            decision=decision,
            direction=resolved["direction"],
            confidence=resolved["confidence"],
            target_price=resolved["target_price"],
            stop_loss_price=resolved["stop_loss_price"],
            result_data=result_data,
            risk_items=risk_items,
            key_metrics=key_metrics,
            analyst_traces=analyst_traces,
            market_report=resolved["market_report"],
            sentiment_report=resolved["sentiment_report"],
            news_report=resolved["news_report"],
            fundamentals_report=resolved["fundamentals_report"],
            macro_report=resolved["macro_report"],
            smart_money_report=resolved["smart_money_report"],
            volume_price_report=resolved["volume_price_report"],
            game_theory_report=resolved["game_theory_report"],
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
    query = db.query(ReportDB).options(load_only(*REPORT_SUMMARY_COLUMNS))
    if user_id:
        query = query.filter(ReportDB.user_id == user_id)
    if symbol:
        query = query.filter(ReportDB.symbol == symbol)
    return query.order_by(ReportDB.created_at.desc()).offset(skip).limit(limit).all()


def get_latest_reports_by_symbols(
    db: Session,
    symbols: List[str],
    user_id: Optional[str] = None,
) -> List[ReportDB]:
    normalized_symbols = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    if not normalized_symbols:
        return []

    query = db.query(ReportDB).options(load_only(*REPORT_SUMMARY_COLUMNS))
    if user_id:
        query = query.filter(ReportDB.user_id == user_id)

    rows = (
        query.filter(ReportDB.symbol.in_(normalized_symbols))
        .order_by(ReportDB.symbol.asc(), ReportDB.created_at.desc())
        .all()
    )

    latest_by_symbol: dict[str, ReportDB] = {}
    for row in rows:
        symbol = str(row.symbol or "").upper()
        if symbol and symbol not in latest_by_symbol:
            latest_by_symbol[symbol] = row

    return [latest_by_symbol[symbol] for symbol in normalized_symbols if symbol in latest_by_symbol]


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


def batch_delete_reports(db: Session, report_ids: Iterable[str], user_id: Optional[str] = None) -> dict:
    normalized_ids: list[str] = []
    seen: set[str] = set()
    for raw_report_id in report_ids:
        report_id = str(raw_report_id or "").strip()
        if not report_id or report_id in seen:
            continue
        seen.add(report_id)
        normalized_ids.append(report_id)

    if not normalized_ids:
        raise ValueError("请至少选择 1 份报告")

    query = db.query(ReportDB).filter(ReportDB.id.in_(normalized_ids))
    if user_id:
        query = query.filter(ReportDB.user_id == user_id)

    rows = query.all()
    row_by_id = {str(row.id): row for row in rows}
    deleted_ids: list[str] = []
    missing_ids: list[str] = []

    for report_id in normalized_ids:
        row = row_by_id.get(report_id)
        if row is None:
            missing_ids.append(report_id)
            continue
        db.delete(row)
        deleted_ids.append(report_id)

    if deleted_ids:
        db.commit()

    return {
        "deleted_ids": deleted_ids,
        "missing_ids": missing_ids,
    }
