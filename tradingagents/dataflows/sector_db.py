"""Local SQLite cache for stock sector & concept mappings.

Stores the relationship between individual stocks and their industry/concept
boards (板块/概念). Data sourced from 东方财富 via akshare.

Usage:
    from tradingagents.dataflows.sector_db import SectorDB

    db = SectorDB()
    db.refresh()  # Full rebuild — takes ~10 min, run weekly

    # Query a stock's sectors
    info = db.get_stock_sectors("600519")
    # {'industry': '白酒', 'concepts': ['白酒概念', '国企改革', ...]}

    # Reverse: which stocks are in a concept
    stocks = db.get_concept_stocks("军工")
    # ['600893', '000768', ...]
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

_DB_DIR = os.path.join(os.path.dirname(__file__), ".cache")
_DB_PATH = os.path.join(_DB_DIR, "sector_concept.db")

# Concepts relevant to geopolitical / macro impact analysis.
# These are pre-filtered from 东方财富's ~483 concept boards.
IMPACT_CONCEPTS = [
    # 军工 & 国防
    "军工", "航天航空", "商业航天", "无人机",
    # 能源 & 大宗
    "油气资源", "油气设服", "天然气", "煤化工概念", "核能核电",
    "黄金概念", "稀土永磁",
    # 新能源
    "新能源", "新能源车", "光伏概念", "锂电池概念", "锂矿概念",
    # 科技 & 芯片
    "半导体概念", "国产芯片", "存储芯片", "光刻机(胶)",
    "第三代半导体", "第四代半导体", "AI芯片", "汽车芯片",
    # AI & 机器人
    "人工智能", "AIGC概念", "AI应用", "AI智能体", "机器人概念",
    "人形机器人", "机器人执行器",
    # 华为 & 自主可控
    "华为概念", "华为昇腾", "华为海思", "华为欧拉", "鸿蒙概念", "信创",
    # 特斯拉 & 汽车
    "特斯拉概念", "汽车整车", "汽车一体化压铸", "汽车热管理", "小米汽车",
    # 贸易 & 一带一路
    "一带一路", "中俄贸易概念",
    # 农业 & 粮食
    "粮食概念", "农业种植", "生态农业",
    # 其他
    "化工原料", "数字货币", "区块链", "卫星互联网",
    "铜缆高速连接",
]


class SectorDB:
    """Thread-safe local cache for stock-sector mappings."""

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_tables(self):
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS stock_industry (
                        stock_code TEXT NOT NULL,
                        stock_name TEXT NOT NULL DEFAULT '',
                        industry   TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (stock_code, industry)
                    );
                    CREATE TABLE IF NOT EXISTS stock_concept (
                        stock_code   TEXT NOT NULL,
                        stock_name   TEXT NOT NULL DEFAULT '',
                        concept_name TEXT NOT NULL,
                        updated_at   TEXT NOT NULL,
                        PRIMARY KEY (stock_code, concept_name)
                    );
                    CREATE TABLE IF NOT EXISTS meta (
                        key   TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_concept_name
                        ON stock_concept(concept_name);
                    CREATE INDEX IF NOT EXISTS idx_industry_name
                        ON stock_industry(industry);
                """)
                conn.commit()
            finally:
                conn.close()

    # ── Query API ───────────────────────────────────────────────────────────

    def get_stock_sectors(self, stock_code: str) -> Dict[str, Any]:
        """Get industry & concepts for a stock. Returns empty if not cached."""
        code = stock_code.replace(".", "").lstrip("0") if len(stock_code) > 6 else stock_code
        # Normalize: keep 6-digit code
        code = stock_code[-6:] if len(stock_code) > 6 else stock_code

        with self._lock:
            conn = self._connect()
            try:
                industries = [
                    row[0] for row in
                    conn.execute("SELECT industry FROM stock_industry WHERE stock_code=?", (code,)).fetchall()
                ]
                concepts = [
                    row[0] for row in
                    conn.execute("SELECT concept_name FROM stock_concept WHERE stock_code=?", (code,)).fetchall()
                ]
                return {"industry": industries, "concepts": concepts}
            finally:
                conn.close()

    def get_concept_stocks(self, concept_name: str) -> List[str]:
        """Get all stock codes in a concept board."""
        with self._lock:
            conn = self._connect()
            try:
                return [
                    row[0] for row in
                    conn.execute("SELECT stock_code FROM stock_concept WHERE concept_name=?",
                                 (concept_name,)).fetchall()
                ]
            finally:
                conn.close()

    def get_industry_stocks(self, industry_name: str) -> List[str]:
        """Get all stock codes in an industry board."""
        with self._lock:
            conn = self._connect()
            try:
                return [
                    row[0] for row in
                    conn.execute("SELECT stock_code FROM stock_industry WHERE industry=?",
                                 (industry_name,)).fetchall()
                ]
            finally:
                conn.close()

    def get_all_concepts(self) -> List[str]:
        """Get all cached concept names."""
        with self._lock:
            conn = self._connect()
            try:
                return [
                    row[0] for row in
                    conn.execute("SELECT DISTINCT concept_name FROM stock_concept ORDER BY concept_name").fetchall()
                ]
            finally:
                conn.close()

    def get_last_refresh(self) -> Optional[str]:
        """Get timestamp of last full refresh."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT value FROM meta WHERE key='last_refresh'").fetchone()
                return row[0] if row else None
            finally:
                conn.close()

    def is_stale(self, max_age_days: int = 7) -> bool:
        """Check if data is older than max_age_days."""
        last = self.get_last_refresh()
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
            return (datetime.now() - last_dt).days >= max_age_days
        except Exception:
            return True

    def stock_count(self) -> int:
        """Count unique stocks in the database."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COUNT(DISTINCT stock_code) FROM stock_concept"
                ).fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    # ── Refresh (rebuild from akshare) ──────────────────────────────────────

    def refresh(
        self,
        concepts: Optional[List[str]] = None,
        include_industry: bool = True,
        progress_callback=None,
    ) -> Dict[str, int]:
        """Rebuild the local cache from akshare.

        By default fetches ALL concept boards (~483) and all industry boards
        (~90) from 东方财富. Data is stored in full so it can be reused for
        any future purpose; filtering happens at query time.

        Args:
            concepts: Explicit list of concept names. If None, fetches all
                      from ``stock_board_concept_name_em()``.
            include_industry: Also fetch industry board mappings.
            progress_callback: Optional callable(current, total, message).

        Returns:
            Dict with counts: {"industries": N, "concepts": N, "stocks": N}
        """
        import akshare as ak

        # Fetch full concept list from 东方财富 when no explicit list given
        if concepts is None:
            try:
                concept_df = ak.stock_board_concept_name_em()
                concepts = concept_df["板块名称"].tolist()
            except Exception:
                concepts = IMPACT_CONCEPTS  # fallback to curated list

        now = datetime.now().isoformat()
        stats = {"industries": 0, "concepts": 0, "stocks": set()}
        total_steps = len(concepts) + (90 if include_industry else 0)
        step = 0

        conn = self._connect()
        try:
            # ── Industry boards (同花顺, ~90) ──
            if include_industry:
                try:
                    industry_df = ak.stock_board_industry_name_ths()
                    industry_names = industry_df["name"].tolist()
                except Exception:
                    industry_names = []

                for ind_name in industry_names:
                    step += 1
                    if progress_callback:
                        progress_callback(step, total_steps, f"行业: {ind_name}")
                    try:
                        df = ak.stock_board_industry_cons_ths(symbol=ind_name)
                        if df is not None and not df.empty:
                            rows = []
                            for _, row in df.iterrows():
                                code = str(row.get("代码", row.get("code", "")))
                                name = str(row.get("名称", row.get("name", "")))
                                if code and code != "nan":
                                    rows.append((code, name, ind_name, now))
                                    stats["stocks"].add(code)
                            conn.executemany(
                                "INSERT OR REPLACE INTO stock_industry VALUES (?,?,?,?)",
                                rows,
                            )
                            stats["industries"] += 1
                    except Exception:
                        pass
                    time.sleep(0.3)  # rate limit

                conn.commit()

            # ── Concept boards (东方财富, selected) ──
            for concept_name in concepts:
                step += 1
                if progress_callback:
                    progress_callback(step, total_steps, f"概念: {concept_name}")
                try:
                    df = ak.stock_board_concept_cons_em(symbol=concept_name)
                    if df is not None and not df.empty:
                        rows = []
                        for _, row in df.iterrows():
                            code = str(row.get("代码", ""))
                            name = str(row.get("名称", ""))
                            if code and code != "nan":
                                rows.append((code, name, concept_name, now))
                                stats["stocks"].add(code)
                        conn.executemany(
                            "INSERT OR REPLACE INTO stock_concept VALUES (?,?,?,?)",
                            rows,
                        )
                        stats["concepts"] += 1
                except Exception:
                    pass
                time.sleep(0.5)  # rate limit — 东方财富 stricter

            conn.execute(
                "INSERT OR REPLACE INTO meta VALUES ('last_refresh', ?)", (now,)
            )
            conn.commit()

        finally:
            conn.close()

        stats["stocks"] = len(stats["stocks"])
        return stats

    # ── Format for LLM ──────────────────────────────────────────────────────

    def format_stock_context(self, stock_code: str) -> str:
        """Format a stock's sector/concept info for the analyst prompt.

        All concepts are listed; those in IMPACT_CONCEPTS are marked with
        a star (*) to help the analyst focus on geopolitically relevant ones.
        """
        info = self.get_stock_sectors(stock_code)
        if not info["industry"] and not info["concepts"]:
            return ""

        impact_set = set(IMPACT_CONCEPTS)
        parts = []
        if info["industry"]:
            parts.append(f"所属行业：{', '.join(info['industry'])}")
        if info["concepts"]:
            tagged = []
            for c in info["concepts"]:
                tagged.append(f"★{c}" if c in impact_set else c)
            parts.append(f"所属概念板块（{len(info['concepts'])}个，★=地缘敏感）：{', '.join(tagged)}")
        return "\n".join(parts)


# ── Module-level singleton ──────────────────────────────────────────────────

_instance: Optional[SectorDB] = None
_instance_lock = threading.Lock()


def get_sector_db() -> SectorDB:
    """Get or create the module-level SectorDB singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SectorDB()
    return _instance
