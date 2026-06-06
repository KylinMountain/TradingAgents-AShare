"""Admin service for user management."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.database import UserDB


def is_admin(user: Optional[UserDB]) -> bool:
    return bool(user and user.is_admin)


def get_all_users(db: Session, skip: int = 0, limit: int = 100) -> list[UserDB]:
    return db.query(UserDB).order_by(UserDB.created_at.desc()).offset(skip).limit(limit).all()


def get_user_count(db: Session) -> int:
    return db.query(UserDB).count()


def get_user_by_id(db: Session, user_id: str) -> Optional[UserDB]:
    return db.query(UserDB).filter(UserDB.id == user_id).first()


def ban_user(db: Session, user_id: str, reason: Optional[str] = None) -> Optional[UserDB]:
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        return None
    user.is_banned = True
    user.ban_reason = reason
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def unban_user(db: Session, user_id: str) -> Optional[UserDB]:
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        return None
    user.is_banned = False
    user.ban_reason = None
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: str) -> bool:
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


def set_admin(db: Session, user_id: str, admin: bool = True) -> Optional[UserDB]:
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        return None
    user.is_admin = admin
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user
