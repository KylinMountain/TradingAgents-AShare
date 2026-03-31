"""Database configuration and session management."""

import os
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import Boolean, create_engine, Column, String, DateTime, Text, Integer, Float, JSON, UniqueConstraint, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Database URL - default to SQLite for simplicity
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tradingagents.db")

# Create engine
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_timeout=60,
        pool_recycle=3600,
    )

    def _can_use_wal() -> bool:
        """Check if WAL mode is safe: db's parent dir must be writable for -shm/-wal files."""
        import pathlib
        db_path = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
        parent = pathlib.Path(db_path).resolve().parent
        return os.access(parent, os.W_OK)

    _use_wal = _can_use_wal()

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        if _use_wal:
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
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
    """Get database session (for FastAPI Depends)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class get_db_ctx:
    """Context manager for manual DB session usage.

    Usage:
        with get_db_ctx() as db:
            db.query(...)
    """

    def __init__(self) -> None:
        self.db: Session | None = None

    def __enter__(self) -> Session:
        self.db = SessionLocal()
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.db is not None:
            if exc_type is not None:
                self.db.rollback()
            self.db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    _ensure_report_schema()
    _ensure_user_schema()


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


def _ensure_user_schema() -> None:
    """Add columns to users table for existing SQLite deployments without migrations."""
    try:
        with engine.begin() as conn:
            columns = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
            if "last_login_ip" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login_ip VARCHAR(45)"))
            if "email_report_enabled" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN email_report_enabled BOOLEAN NOT NULL DEFAULT 1"))
    except Exception as e:
        print(f"Warning: Failed to ensure user schema: {e}")

    _migrate_tokens_to_hashed()
    _migrate_api_keys_reencrypt()


def _migrate_tokens_to_hashed() -> None:
    """Migrate plaintext API tokens to HMAC-SHA256 hashed storage."""
    import hashlib, hmac
    try:
        with engine.begin() as conn:
            # Add token_hint column if missing
            token_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(user_tokens)"))}
            if "token_hint" not in token_cols:
                conn.execute(text("ALTER TABLE user_tokens ADD COLUMN token_hint VARCHAR(8)"))

            # Detect un-migrated rows: plaintext tokens start with "ta-sk-"
            rows = conn.execute(text("SELECT id, token FROM user_tokens WHERE token LIKE 'ta-sk-%'")).fetchall()
            if not rows:
                return
            from api.services.auth_service import _secret_key
            key = _secret_key().encode("utf-8")
            for row_id, plaintext in rows:
                token_hash = hmac.new(key, plaintext.encode("utf-8"), hashlib.sha256).hexdigest()
                hint = plaintext[-4:]
                conn.execute(
                    text("UPDATE user_tokens SET token = :hash, token_hint = :hint WHERE id = :id"),
                    {"hash": token_hash, "hint": hint, "id": row_id},
                )
            print(f"[security] Migrated {len(rows)} API tokens from plaintext to hashed storage.")
    except Exception as e:
        print(f"Warning: Token hash migration failed: {e}")


def _migrate_api_keys_reencrypt() -> None:
    """Re-encrypt user API keys when TA_APP_SECRET_KEY changes.

    On startup, if a custom secret is configured, tries to decrypt each key
    with the current secret. If that fails, tries the default secret (old data).
    If the default key works, re-encrypts with the current key and writes back.
    """
    from api.services.auth_service import (
        is_custom_secret_configured, decrypt_secret,
        decrypt_secret_with_fallback, encrypt_secret,
    )
    if not is_custom_secret_configured():
        return
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT user_id, api_key_encrypted FROM user_llm_configs WHERE api_key_encrypted IS NOT NULL")
            ).fetchall()
            if not rows:
                return
            # Quick check: if the first row decrypts fine, likely all are OK already.
            first_user_id, first_encrypted = rows[0]
            if decrypt_secret(first_encrypted) is not None and len(rows) < 50:
                # Small dataset, still verify all — but for large sets, skip if first is OK
                pass
            migrated = 0
            for user_id, encrypted in rows:
                # Already decryptable with current key — skip
                if decrypt_secret(encrypted) is not None:
                    continue
                # Try fallback (old key or default key)
                plaintext = decrypt_secret_with_fallback(encrypted)
                if plaintext is None:
                    print(f"[security] WARNING: Cannot decrypt API key for user {user_id} with any known key. Skipping.")
                    continue
                # Re-encrypt with current key
                new_encrypted = encrypt_secret(plaintext)
                conn.execute(
                    text("UPDATE user_llm_configs SET api_key_encrypted = :enc WHERE user_id = :uid"),
                    {"enc": new_encrypted, "uid": user_id},
                )
                migrated += 1
            if migrated:
                print(f"[security] Re-encrypted {migrated} API key(s) with new TA_APP_SECRET_KEY.")
    except Exception as e:
        print(f"Warning: API key re-encryption migration failed: {e}")


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
    direction = Column(String(50), nullable=True)  # 看多、偏多、中性、偏空、看空
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
    last_login_ip = Column(String(45), nullable=True)
    email_report_enabled = Column(Boolean, default=True, nullable=False, server_default="1")


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
    token_hint = Column(String(8), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class VersionStatsDB(Base):
    __tablename__ = "version_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=True)
    nonce = Column(String(64), nullable=True)
    remote_ip = Column(String(45), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class WatchlistItemDB(Base):
    """User watchlist items."""
    __tablename__ = "watchlist_items"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(64), index=True, nullable=False)
    symbol = Column(String(20), nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint('user_id', 'symbol', name='uq_watchlist_user_symbol'),)


class ScheduledAnalysisDB(Base):
    """Scheduled daily analysis tasks."""
    __tablename__ = "scheduled_analyses"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(64), index=True, nullable=False)
    symbol = Column(String(20), nullable=False)
    horizon = Column(String(10), default="short")
    trigger_time = Column(String(5), default="20:00")
    is_active = Column(Boolean, default=True)
    last_run_date = Column(String(10), nullable=True)
    last_run_status = Column(String(10), nullable=True)
    last_report_id = Column(String(36), nullable=True)
    consecutive_failures = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint('user_id', 'symbol', name='uq_scheduled_user_symbol'),)


class ThsImportConfigDB(Base):
    """Latest TongHuaShun local import state for each user."""

    __tablename__ = "ths_import_configs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(64), index=True, nullable=False, unique=True)
    holdings_filename = Column(String(255), nullable=True)
    trades_filename = Column(String(255), nullable=True)
    auto_apply_scheduled = Column(Boolean, default=True, nullable=False)
    last_imported_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ImportedPortfolioPositionDB(Base):
    """Imported current holdings snapshot plus recent trade points for a symbol."""

    __tablename__ = "imported_portfolio_positions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(64), index=True, nullable=False)
    source = Column(String(32), default="ths_local", nullable=False)
    symbol = Column(String(20), nullable=False)
    security_name = Column(String(80), nullable=True)
    current_position = Column(Float, nullable=True)
    available_position = Column(Float, nullable=True)
    average_cost = Column(Float, nullable=True)
    market_value = Column(Float, nullable=True)
    current_position_pct = Column(Float, nullable=True)
    trade_points_json = Column(JSON, nullable=True)
    trade_points_count = Column(Integer, default=0, nullable=False)
    latest_trade_at = Column(String(32), nullable=True)
    latest_trade_action = Column(String(16), nullable=True)
    last_imported_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('user_id', 'source', 'symbol', name='uq_imported_portfolio_user_source_symbol'),
    )


class QmtImportConfigDB(Base):
    """Latest QMT / xtquant sync configuration for each user."""

    __tablename__ = "qmt_import_configs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(64), index=True, nullable=False, unique=True)
    qmt_path = Column(String(500), nullable=False)
    account_id = Column(String(64), nullable=False)
    account_type = Column(String(32), default="STOCK", nullable=False)
    auto_apply_scheduled = Column(Boolean, default=True, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
