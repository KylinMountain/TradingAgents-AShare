"""Feedback service: user-side CRUD operations.

Admin reply and email notification are handled by the separate admin project.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from api.database import FeedbackDB, UserDB

logger = logging.getLogger(__name__)


def create_feedback(db: Session, user: UserDB, subject: str, content: str) -> FeedbackDB:
    fb = FeedbackDB(
        id=str(uuid4()),
        user_id=user.id,
        user_email=user.email,
        subject=subject,
        content=content,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def list_feedbacks(db: Session, user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[FeedbackDB], int]:
    q = db.query(FeedbackDB).filter(FeedbackDB.user_id == user_id).order_by(FeedbackDB.created_at.desc())
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def get_feedback(db: Session, feedback_id: str) -> Optional[FeedbackDB]:
    return db.query(FeedbackDB).filter(FeedbackDB.id == feedback_id).first()


def mark_read(db: Session, feedback_id: str, user_id: str) -> Optional[FeedbackDB]:
    fb = db.query(FeedbackDB).filter(FeedbackDB.id == feedback_id, FeedbackDB.user_id == user_id).first()
    if fb:
        fb.is_read = True
        db.commit()
        db.refresh(fb)
    return fb


def unread_count(db: Session, user_id: str) -> int:
    return db.query(FeedbackDB).filter(
        FeedbackDB.user_id == user_id,
        FeedbackDB.admin_reply.isnot(None),
        FeedbackDB.is_read.is_(False),
    ).count()
