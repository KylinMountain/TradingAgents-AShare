"""Database configuration and session management."""

import os
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import Boolean, create_engine, Column, String, DateTime, Text, Integer, Float, JSON, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Database URL - default to SQLite for simplicity
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tradingagents.db")

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    # For PostgreSQL/MySQL, use a larger pool to handle concurrency
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=20,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    _ensure_report_schema()


def _ensure_report_schema() -> None:
    """Add lightweight columns for existing SQLite deployments without migrations."""
    try:
        with engine.begin() as conn:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(reports)"))}
            if "direction" not in columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN direction VARCHAR(50)"))
            if "status" not in columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN status VARCHAR(20) DEFAULT 'completed'"))
            if "error" not in columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN error TEXT"))
            if "analyst_traces" not in columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN analyst_traces JSON"))
            if "macro_report" not in columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN macro_report TEXT"))
            if "smart_money_report" not in columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN smart_money_report TEXT"))
            if "game_theory_report" not in columns:
                conn.execute(text("ALTER TABLE reports ADD COLUMN game_theory_report TEXT"))
    except Exception as e:
        print(f"Warning: Failed to ensure report schema: {e}")


# Report Model
class ReportDB(Base):
    """Report database model."""
    
    __tablename__ = "reports"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(64), index=True, nullable=True)  # For future multi-user support
    symbol = Column(String(20), index=True, nullable=False)
    trade_date = Column(String(10), nullable=False)
    
    # Task lifecycle info
    status = Column(String(20), default="completed", index=True)  # pending, running, completed, failed
    error = Column(Text, nullable=True)
    
    # Decision info
    decision = Column(String(50), nullable=True)  # BUY, SELL, HOLD, etc.
    direction = Column(String(50), nullable=True)  # 看多、看空、中性、谨慎
    confidence = Column(Integer, nullable=True)  # 0-100
    target_price = Column(Float, nullable=True)
    stop_loss_price = Column(Float, nullable=True)
    
    # Full analysis results stored as JSON
    result_data = Column(JSON, nullable=True)

    # LLM-extracted structured data
    risk_items = Column(JSON, nullable=True)   # [{"name": "...", "level": "high|medium|low", "description": "..."}]
    key_metrics = Column(JSON, nullable=True)  # [{"name": "...", "value": "...", "status": "good|neutral|bad"}]
    analyst_traces = Column(JSON, nullable=True) # [{"agent": "...", "verdict": "...", "key_finding": "..."}]

    # Individual reports (for quick access)
    market_report = Column(Text, nullable=True)
    sentiment_report = Column(Text, nullable=True)
    news_report = Column(Text, nullable=True)
    fundamentals_report = Column(Text, nullable=True)
    macro_report = Column(Text, nullable=True)
    smart_money_report = Column(Text, nullable=True)
    game_theory_report = Column(Text, nullable=True)
    investment_plan = Column(Text, nullable=True)
    trader_investment_plan = Column(Text, nullable=True)
    final_trade_decision = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "trade_date": self.trade_date,
            "decision": self.decision,
            "direction": self.direction,
            "confidence": self.confidence,
            "target_price": self.target_price,
            "stop_loss_price": self.stop_loss_price,
            "result_data": self.result_data,
            "risk_items": self.risk_items,
            "key_metrics": self.key_metrics,
            "analyst_traces": self.analyst_traces,
            "market_report": self.market_report,
            "sentiment_report": self.sentiment_report,
            "news_report": self.news_report,
            "fundamentals_report": self.fundamentals_report,
            "macro_report": self.macro_report,
            "smart_money_report": self.smart_money_report,
            "game_theory_report": self.game_theory_report,
            "investment_plan": self.investment_plan,
            "trader_investment_plan": self.trader_investment_plan,
            "final_trade_decision": self.final_trade_decision,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserDB(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime, nullable=True)


class EmailVerificationCodeDB(Base):
    __tablename__ = "email_verification_codes"

    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    code_hash = Column(String(255), nullable=False)
    purpose = Column(String(50), default="login", nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserLLMConfigDB(Base):
    __tablename__ = "user_llm_configs"

    user_id = Column(String(36), primary_key=True, index=True)
    llm_provider = Column(String(50), nullable=True)
    backend_url = Column(String(500), nullable=True)
    quick_think_llm = Column(String(255), nullable=True)
    deep_think_llm = Column(String(255), nullable=True)
    max_debate_rounds = Column(Integer, nullable=True)
    max_risk_discuss_rounds = Column(Integer, nullable=True)
    api_key_encrypted = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class UserTokenDB(Base):
    __tablename__ = "user_tokens"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), index=True, nullable=False)
    name = Column(String(50), nullable=False)
    token = Column(String(128), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
