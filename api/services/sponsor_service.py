"""Sponsor service: public read operations.

Sponsor records are managed by the admin project directly in the database.
This service only provides read access for the public-facing thanks page.
The `amount` field is intentionally excluded from all public queries.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from api.database import SponsorDB

logger = logging.getLogger(__name__)


def list_sponsors(db: Session, sponsor_type: Optional[str] = None) -> list[SponsorDB]:
    """List visible sponsors, optionally filtered by type (money/token)."""
    q = db.query(SponsorDB).filter(SponsorDB.is_visible.is_(True))
    if sponsor_type:
        q = q.filter(SponsorDB.sponsor_type == sponsor_type)
    return q.order_by(SponsorDB.sort_order.asc(), SponsorDB.date.desc()).all()
