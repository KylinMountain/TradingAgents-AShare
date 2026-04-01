"""Lightweight geopolitical & macro event fetcher.

Pulls data from free RSS feeds and public APIs — **no RSSHub required**.
Uses only ``requests`` (already a project dependency) + stdlib ``xml``.
"""

from __future__ import annotations

import re
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

_TIMEOUT = 12  # seconds per request
_LOCK = threading.Lock()

# ── RSS Sources ──────────────────────────────────────────────────────────────

_RSS_SOURCES: List[Dict[str, str]] = [
    {
        "name": "Trump Truth Social",
        "url": "https://www.trumpstruth.org/feed",
        "type": "rss",
        "category": "trump",
    },
    {
        "name": "Reuters World",
        "url": "https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best",
        "type": "rss",
        "category": "geopolitical",
    },
    {
        "name": "BBC World",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "type": "rss",
        "category": "geopolitical",
    },
    {
        "name": "AP News",
        "url": "https://feedx.net/rss/ap.xml",
        "type": "rss",
        "category": "geopolitical",
    },
]

# ── Helpers ──────────────────────────────────────────────────────────────────


def _parse_rss(xml_text: str, limit: int = 20) -> List[Dict[str, str]]:
    """Parse RSS/Atom XML into a list of {title, link, published, summary}."""
    items: List[Dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # RSS 2.0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        # Strip HTML tags from description
        desc = re.sub(r"<[^>]+>", "", desc)[:300]
        if title:
            items.append({"title": title, "link": link, "published": pub, "summary": desc})
        if len(items) >= limit:
            return items

    # Atom fallback
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", ns):
        title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
        link_el = entry.find("atom:link", ns)
        link = (link_el.get("href", "") if link_el is not None else "").strip()
        pub = (entry.findtext("atom:published", namespaces=ns) or
               entry.findtext("atom:updated", namespaces=ns) or "").strip()
        desc = (entry.findtext("atom:summary", namespaces=ns) or "").strip()
        desc = re.sub(r"<[^>]+>", "", desc)[:300]
        if title:
            items.append({"title": title, "link": link, "published": pub, "summary": desc})
        if len(items) >= limit:
            return items

    return items


def _fetch_url(url: str) -> Optional[str]:
    """GET with timeout; returns body or None on failure."""
    try:
        resp = requests.get(
            url,
            timeout=_TIMEOUT,
            headers={"User-Agent": "TradingAgents-AShare/1.0 (geopolitical-monitor)"},
        )
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


# ── 华尔街见闻 (WallStreetCN) live flash API ────────────────────────────────

_WALLSTREETCN_API = "https://api-one-wscn.awtmt.com/apiv1/content/lives"


def _fetch_wallstreetcn(limit: int = 30) -> List[Dict[str, str]]:
    """Fetch live flash news from 华尔街见闻 public API."""
    items: List[Dict[str, str]] = []
    try:
        resp = requests.get(
            _WALLSTREETCN_API,
            params={"channel": "global-channel", "limit": limit},
            timeout=_TIMEOUT,
            headers={"User-Agent": "TradingAgents-AShare/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        for item in (data.get("data", {}).get("items", []))[:limit]:
            title = item.get("title", "") or item.get("content_text", "")
            # content_text is HTML-like, strip tags
            title = re.sub(r"<[^>]+>", "", title).strip()
            if not title:
                continue
            pub_ts = item.get("display_time", 0)
            pub_str = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d %H:%M") if pub_ts else ""
            items.append({
                "title": title[:200],
                "link": item.get("uri", ""),
                "published": pub_str,
                "summary": "",
            })
    except Exception:
        pass
    return items


# ── 财联社电报 (via akshare) ─────────────────────────────────────────────────

def _fetch_cls_telegraph(limit: int = 30) -> List[Dict[str, str]]:
    """Fetch 财联社 telegraph/flash news via akshare."""
    items: List[Dict[str, str]] = []
    try:
        import akshare as ak
        df = ak.stock_telegraph_cls()
        if df is None or df.empty:
            return items
        for _, row in df.head(limit).iterrows():
            title = str(row.get("标题", row.get("title", "")))
            content = str(row.get("内容", row.get("content", "")))
            pub = str(row.get("发布时间", row.get("datetime", "")))
            if title and title != "nan":
                items.append({
                    "title": title[:200],
                    "link": "",
                    "published": pub,
                    "summary": content[:300] if content != "nan" else "",
                })
    except Exception:
        pass
    return items


# ── Public API ───────────────────────────────────────────────────────────────

def fetch_geopolitical_news(
    limit_per_source: int = 15,
    categories: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Fetch geopolitical news from all configured sources.

    Returns a dict with:
      - ``trump``: List of Trump Truth Social posts
      - ``geopolitical``: List of international news items
      - ``cn_flash``: List of Chinese financial flash news
      - ``formatted``: A single formatted string ready for LLM consumption
    """
    if categories is None:
        categories = ["trump", "geopolitical", "cn_flash"]

    result: Dict[str, List[Dict[str, str]]] = {
        "trump": [],
        "geopolitical": [],
        "cn_flash": [],
    }

    # ── Fetch RSS sources in sequence (thread-safe) ──
    if "trump" in categories or "geopolitical" in categories:
        with _LOCK:
            for src in _RSS_SOURCES:
                if src["category"] not in categories:
                    continue
                body = _fetch_url(src["url"])
                if body:
                    items = _parse_rss(body, limit=limit_per_source)
                    for item in items:
                        item["source"] = src["name"]
                    result[src["category"]].extend(items)

    # ── Chinese flash news ──
    if "cn_flash" in categories:
        wscn = _fetch_wallstreetcn(limit=limit_per_source)
        for item in wscn:
            item["source"] = "华尔街见闻"
        result["cn_flash"].extend(wscn)

        cls_items = _fetch_cls_telegraph(limit=limit_per_source)
        for item in cls_items:
            item["source"] = "财联社电报"
        result["cn_flash"].extend(cls_items)

    # ── Format for LLM ──
    result["formatted"] = _format_for_llm(result)
    return result


def _format_for_llm(data: Dict[str, List[Dict[str, str]]]) -> str:
    """Format fetched data into a single string for the analyst prompt."""
    sections: List[str] = []

    if data.get("trump"):
        lines = ["## 特朗普 Truth Social 最新发言"]
        for i, item in enumerate(data["trump"][:10], 1):
            lines.append(f"{i}. [{item['published']}] {item['title']}")
            if item.get("summary"):
                lines.append(f"   > {item['summary']}")
        sections.append("\n".join(lines))

    if data.get("geopolitical"):
        lines = ["## 国际地缘政治新闻"]
        for i, item in enumerate(data["geopolitical"][:15], 1):
            lines.append(f"{i}. [{item.get('source', '')}] {item['title']}")
            if item.get("summary"):
                lines.append(f"   > {item['summary']}")
        sections.append("\n".join(lines))

    if data.get("cn_flash"):
        lines = ["## 中文财经快讯（华尔街见闻 + 财联社）"]
        for i, item in enumerate(data["cn_flash"][:20], 1):
            src = item.get("source", "")
            lines.append(f"{i}. [{src} {item['published']}] {item['title']}")
        sections.append("\n".join(lines))

    if not sections:
        return "暂无地缘政治与外部冲击相关数据。"

    return "\n\n".join(sections)
