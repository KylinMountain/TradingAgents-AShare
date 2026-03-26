from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session
from api.database import UserTokenDB, UserDB


TOKEN_PREFIX = "ta-sk-"
MAX_TOKENS_PER_USER = 10


def _hmac_key() -> bytes:
    from api.services.auth_service import _secret_key
    return _secret_key().encode("utf-8")


def _hash_token(token_str: str) -> str:
    """HMAC-SHA256 hash — prevents offline brute-force even if DB is leaked."""
    return hmac.new(_hmac_key(), token_str.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_token_string() -> str:
    """Generate a secure random token with prefix."""
    random_part = secrets.token_urlsafe(64)
    return f"{TOKEN_PREFIX}{random_part}"


def create_token(db: Session, user_id: str, name: str) -> dict:
    """Create a new API token for a user.

    Returns a dict with the full token (shown once) and DB metadata.
    """
    count = db.query(UserTokenDB).filter(UserTokenDB.user_id == user_id).count()
    if count >= MAX_TOKENS_PER_USER:
        raise ValueError(f"每个用户最多只能创建 {MAX_TOKENS_PER_USER} 个 API Token")

    plaintext = generate_token_string()
    new_token = UserTokenDB(
        id=str(uuid4()),
        user_id=user_id,
        name=name,
        token=_hash_token(plaintext),
        token_hint=plaintext[-4:],
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_token)
    db.commit()
    db.refresh(new_token)
    # Return the plaintext token once; it is never stored.
    return {
        "id": new_token.id,
        "name": new_token.name,
        "token": plaintext,
        "token_hint": new_token.token_hint,
        "last_used_at": new_token.last_used_at,
        "created_at": new_token.created_at,
    }


def list_user_tokens(db: Session, user_id: str) -> List[UserTokenDB]:
    """List all tokens for a user."""
    return db.query(UserTokenDB).filter(UserTokenDB.user_id == user_id).order_by(UserTokenDB.created_at.desc()).all()


def delete_token(db: Session, user_id: str, token_id: str) -> bool:
    """Delete (revoke) a token."""
    token_row = db.query(UserTokenDB).filter(
        UserTokenDB.id == token_id,
        UserTokenDB.user_id == user_id
    ).first()

    if not token_row:
        return False

    db.delete(token_row)
    db.commit()
    return True


def verify_token(db: Session, token_str: str) -> Optional[UserDB]:
    """Verify a token string and return the associated user."""
    if not token_str.startswith(TOKEN_PREFIX):
        return None

    token_hash = _hash_token(token_str)
    token_row = db.query(UserTokenDB).filter(
        UserTokenDB.token == token_hash,
        UserTokenDB.is_active == True
    ).first()

    if not token_row:
        return None

    # Update last used
    token_row.last_used_at = datetime.now(timezone.utc)
    db.commit()

    # Get user
    return db.query(UserDB).filter(UserDB.id == token_row.user_id).first()
