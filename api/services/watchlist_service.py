"""Watchlist service for database operations."""

import json
import logging
from typing import List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from api.database import WatchlistItemDB, ScheduledAnalysisDB

logger = logging.getLogger(__name__)

MAX_WATCHLIST_ITEMS = 50
MAX_CONCEPTS = 5  # 最多显示5个概念


def _to_xq_symbol(symbol: str) -> str:
    """Convert 6-digit code to Xueqiu format (e.g., 'SH600519')."""
    s = symbol.strip()
    if s.startswith(("6", "9")):
        return f"SH{s}"
    return f"SZ{s}"


def fetch_stock_concepts(symbol: str) -> List[dict]:
    """Fetch concept/industry boards for a stock from THS/Xueqiu.

    Returns list of {"name": str, "type": str} sorted by priority:
    行业 > 概念 > 地域, max 5 items.
    """
    try:
        import akshare as ak
        xq_symbol = _to_xq_symbol(symbol)
        df = ak.stock_individual_basic_info_xq(symbol=xq_symbol)
        if df is None or df.empty:
            return []

        items = dict(zip(df["item"].astype(str), df["value"].astype(str)))
        concepts = []

        # 行业 (最高优先级)
        if "行业" in items and items["行业"]:
            for name in items["行业"].split("+")[:2]:  # 最多2个行业
                name = name.strip()
                if name:
                    concepts.append({"name": name, "type": "行业"})

        # 概念
        if "概念" in items and items["概念"]:
            for name in items["概念"].split("+")[:2]:  # 最多2个概念
                name = name.strip()
                if name:
                    concepts.append({"name": name, "type": "概念"})

        # 地域 (最低优先级)
        if "地域" in items and items["地域"]:
            concepts.append({"name": items["地域"], "type": "地域"})

        # 上市板块 (补充)
        if "上市板块" in items and items["上市板块"] and len(concepts) < MAX_CONCEPTS:
            concepts.append({"name": items["上市板块"], "type": "板块"})

        return concepts[:MAX_CONCEPTS]
    except Exception as e:
        logger.debug("Failed to fetch concepts for %s: %s", symbol, e)
        return []


def get_concepts_from_db(db: Session, item_id: str) -> List[dict]:
    """Get concepts from database for a watchlist item."""
    item = db.query(WatchlistItemDB).filter(WatchlistItemDB.id == item_id).first()
    if not item or not item.concepts:
        return []
    try:
        return json.loads(item.concepts)
    except (json.JSONDecodeError, TypeError):
        return []


def update_concepts_in_db(db: Session, item_id: str, concepts: List[dict]) -> None:
    """Update concepts in database for a watchlist item."""
    item = db.query(WatchlistItemDB).filter(WatchlistItemDB.id == item_id).first()
    if item:
        item.concepts = json.dumps(concepts, ensure_ascii=False)
        db.commit()


def refresh_stock_concepts(db: Session, item_id: str) -> List[dict]:
    """Refresh concepts for a single watchlist item."""
    item = db.query(WatchlistItemDB).filter(WatchlistItemDB.id == item_id).first()
    if not item:
        return []
    concepts = fetch_stock_concepts(item.symbol)
    if concepts:
        update_concepts_in_db(db, item_id, concepts)
    return concepts


def refresh_all_concepts(db: Session, user_id: str) -> int:
    """Refresh concepts for all watchlist items. Returns count of updated items."""
    items = db.query(WatchlistItemDB).filter(WatchlistItemDB.user_id == user_id).all()
    updated = 0
    for item in items:
        concepts = fetch_stock_concepts(item.symbol)
        if concepts:
            item.concepts = json.dumps(concepts, ensure_ascii=False)
            updated += 1
    if updated:
        db.commit()
    return updated


def list_watchlist(db: Session, user_id: str) -> List[dict]:
    """List user's watchlist items with scheduled status and concepts."""
    items = (
        db.query(WatchlistItemDB)
        .filter(WatchlistItemDB.user_id == user_id)
        .order_by(WatchlistItemDB.sort_order, WatchlistItemDB.created_at)
        .all()
    )
    scheduled_symbols = set(
        row.symbol for row in
        db.query(ScheduledAnalysisDB.symbol)
        .filter(ScheduledAnalysisDB.user_id == user_id)
        .all()
    )
    return [
        {
            "id": item.id,
            "symbol": item.symbol,
            "sort_order": item.sort_order,
            "notes": item.notes or "",
            "concepts": json.loads(item.concepts) if item.concepts else [],
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "has_scheduled": item.symbol in scheduled_symbols,
        }
        for item in items
    ]


def add_watchlist_item(db: Session, user_id: str, symbol: str) -> dict:
    """Add a stock to user's watchlist and fetch its concepts."""
    count = db.query(WatchlistItemDB).filter(WatchlistItemDB.user_id == user_id).count()
    if count >= MAX_WATCHLIST_ITEMS:
        raise ValueError(f"自选股数量已达上限 ({MAX_WATCHLIST_ITEMS})")

    existing = (
        db.query(WatchlistItemDB)
        .filter(WatchlistItemDB.user_id == user_id, WatchlistItemDB.symbol == symbol)
        .first()
    )
    if existing:
        raise ValueError(f"{symbol} 已在自选列表中")

    # Fetch concepts first (may fail, that's OK)
    concepts = fetch_stock_concepts(symbol)

    item = WatchlistItemDB(
        id=uuid4().hex,
        user_id=user_id,
        symbol=symbol,
        concepts=json.dumps(concepts, ensure_ascii=False) if concepts else "[]",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "symbol": item.symbol,
        "sort_order": item.sort_order,
        "notes": item.notes or "",
        "concepts": concepts,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def add_watchlist_items(db: Session, user_id: str, symbols: List[str]) -> List[dict]:
    """Add multiple stocks to user's watchlist and return per-item results."""
    results: List[dict] = []
    for symbol in symbols:
        try:
            item = add_watchlist_item(db, user_id, symbol)
            results.append({
                "symbol": symbol,
                "status": "added",
                "item": item,
                "message": "已添加到自选列表",
            })
        except ValueError as exc:
            message = str(exc)
            status = "duplicate" if "已在自选列表" in message else "failed"
            results.append({
                "symbol": symbol,
                "status": status,
                "message": message,
            })
    return results


def update_watchlist_notes(db: Session, user_id: str, item_id: str, notes: str) -> bool:
    """Update notes for a watchlist item. Returns True if found and updated."""
    item = (
        db.query(WatchlistItemDB)
        .filter(WatchlistItemDB.id == item_id, WatchlistItemDB.user_id == user_id)
        .first()
    )
    if not item:
        return False
    item.notes = notes[:200] if notes else ""
    db.commit()
    return True


def delete_watchlist_item(db: Session, user_id: str, item_id: str) -> bool:
    """Delete a watchlist item. Returns True if found and deleted."""
    item = (
        db.query(WatchlistItemDB)
        .filter(WatchlistItemDB.id == item_id, WatchlistItemDB.user_id == user_id)
        .first()
    )
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True
