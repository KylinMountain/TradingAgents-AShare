"""Lightweight geopolitical & macro event fetcher.

Pulls data from free RSS feeds and public APIs — **no RSSHub required**.
Uses only ``requests`` (already a project dependency) + stdlib ``xml``.

Covers:
- Trump Truth Social posts (tariffs, sanctions)
- Elon Musk social activity (Tesla, SpaceX, DOGE implications)
- International geopolitical news (CNBC, Al Jazeera, AP, France24)
- Chinese domestic policy (国务院、证监会、央行 via 华尔街见闻 & 财联社)
"""

from __future__ import annotations

import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

_TIMEOUT = 12  # seconds per request

# ── TTL Cache ────────────────────────────────────────────────────────────────
# Avoids hammering sources on repeated calls within the same analysis window.

_CACHE_TTL = 300  # 5 minutes
_cache_lock = threading.Lock()
_cache: Dict[str, Any] = {}  # key → {"ts": float, "data": ...}


def _get_cached(key: str) -> Optional[Any]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
            return entry["data"]
    return None


def _set_cached(key: str, data: Any) -> None:
    with _cache_lock:
        _cache[key] = {"ts": time.time(), "data": data}

# ── RSS Sources ──────────────────────────────────────────────────────────────

_RSS_SOURCES: List[Dict[str, str]] = [
    # ── Key Influencers ──
    {
        "name": "Trump Truth Social",
        "url": "https://www.trumpstruth.org/feed",
        "type": "rss",
        "category": "trump",
    },
    # ── International Geopolitics ──
    {
        "name": "CNBC World",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
        "type": "rss",
        "category": "geopolitical",
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "type": "rss",
        "category": "geopolitical",
    },
    {
        "name": "AP News",
        "url": "https://feedx.net/rss/ap.xml",
        "type": "rss",
        "category": "geopolitical",
    },
    {
        "name": "France24",
        "url": "https://www.france24.com/en/rss",
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


# ── Keyword-based extraction from bulk Chinese flash news ───────────────────

_MUSK_KEYWORDS = ["马斯克", "Musk", "特斯拉", "Tesla", "SpaceX", "DOGE部门",
                  "星链", "Starlink", "xAI", "Grok", "Neuralink"]

_POLICY_KEYWORDS = ["国务院", "证监会", "央行", "发改委", "财政部", "工信部",
                    "住建部", "政治局", "常务会议", "降准", "降息", "LPR",
                    "MLF", "逆回购", "再贷款", "专项债", "产业政策",
                    "银保监", "金融监管", "注册制"]


def _filter_by_keywords(
    items: List[Dict[str, str]],
    keywords: List[str],
    limit: int = 15,
) -> List[Dict[str, str]]:
    """Filter news items by keyword match on title field."""
    matched = []
    for item in items:
        text = item.get("title", "")
        if any(kw in text for kw in keywords):
            matched.append(item)
            if len(matched) >= limit:
                break
    return matched


def _fetch_wallstreetcn_bulk(limit: int = 100) -> List[Dict[str, str]]:
    """Fetch a large batch from 华尔街见闻 for keyword filtering."""
    cache_key = "wscn_bulk"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

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
            title = re.sub(r"<[^>]+>", "", title).strip()
            if not title:
                continue
            pub_ts = item.get("display_time", 0)
            pub_str = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d %H:%M") if pub_ts else ""
            items.append({
                "title": title[:300],
                "link": item.get("uri", ""),
                "published": pub_str,
                "summary": "",
                "source": "华尔街见闻",
            })
    except Exception:
        pass

    _set_cached(cache_key, items)
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
      - ``musk``: List of Elon Musk social posts
      - ``geopolitical``: List of international news items
      - ``cn_policy``: List of Chinese government policy items
      - ``cn_flash``: List of Chinese financial flash news
      - ``formatted``: A single formatted string ready for LLM consumption
    """
    if categories is None:
        categories = ["trump", "musk", "geopolitical", "cn_policy", "cn_flash"]

    # Return cached result if still fresh (avoids rate-limiting)
    cache_key = f"geo:{limit_per_source}:{','.join(sorted(categories))}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    result: Dict[str, List[Dict[str, str]]] = {
        "trump": [],
        "musk": [],
        "geopolitical": [],
        "cn_policy": [],
        "cn_flash": [],
    }

    # ── Fetch all sources in parallel ──
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_rss_source(src):
        body = _fetch_url(src["url"])
        if not body:
            return src["category"], src["name"], []
        items = _parse_rss(body, limit=limit_per_source)
        for item in items:
            item["source"] = src["name"]
        return src["category"], src["name"], items

    futures = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        # RSS feeds (trump, musk, geopolitical, cn_policy)
        for src in _RSS_SOURCES:
            if src["category"] not in categories:
                continue
            futures.append(executor.submit(_fetch_rss_source, src))

        # Chinese flash news (also feeds keyword filtering for musk/policy)
        if any(c in categories for c in ("cn_flash", "musk", "cn_policy")):
            futures.append(executor.submit(
                lambda: ("_bulk", "华尔街见闻", _fetch_wallstreetcn_bulk(limit=100))
            ))
        if "cn_flash" in categories:
            futures.append(executor.submit(
                lambda: ("cn_flash", "华尔街见闻", _fetch_wallstreetcn(limit=limit_per_source))
            ))
            futures.append(executor.submit(
                lambda: ("cn_flash", "财联社电报", _fetch_cls_telegraph(limit=limit_per_source))
            ))

        bulk_items: List[Dict[str, str]] = []
        for future in as_completed(futures):
            try:
                cat, source_name, items = future.result()
                for item in items:
                    item.setdefault("source", source_name)
                if cat == "_bulk":
                    bulk_items = items
                else:
                    result.setdefault(cat, []).extend(items)
            except Exception:
                pass

    # ── Keyword-based extraction from bulk Chinese news ──
    if "musk" in categories and bulk_items:
        result["musk"].extend(_filter_by_keywords(bulk_items, _MUSK_KEYWORDS, limit=limit_per_source))
    if "cn_policy" in categories and bulk_items:
        result["cn_policy"].extend(_filter_by_keywords(bulk_items, _POLICY_KEYWORDS, limit=limit_per_source))

    # ── Format for LLM ──
    result["formatted"] = _format_for_llm(result)
    _set_cached(cache_key, result)
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

    if data.get("musk"):
        lines = ["## 马斯克最新动态"]
        for i, item in enumerate(data["musk"][:10], 1):
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

    if data.get("cn_policy"):
        lines = ["## 中国政府政策动态"]
        for i, item in enumerate(data["cn_policy"][:10], 1):
            lines.append(f"{i}. [{item['published']}] {item['title']}")
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
