"""Pre-market briefing service: data aggregation + LLM trading advice synthesis."""

import asyncio
import io
import json
import logging
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

# ── Aggressively clear ALL proxy env vars before any HTTP library imports ──
for _pv in list(os.environ.keys()):
    if "proxy" in _pv.lower():
        os.environ.pop(_pv, None)
os.environ["NO_PROXY"] = "*"

import requests

# Monkey-patch: force requests to never use system proxy (trust_env bypasses Windows registry proxy)
_ORIG_REQUESTS_GET = requests.get
_ORIG_REQUESTS_POST = requests.post

def _no_proxy_get(url, **kwargs):
    kwargs.setdefault("timeout", 15)
    kwargs["proxies"] = {"http": None, "https": None}
    return _ORIG_REQUESTS_GET(url, **kwargs)

def _no_proxy_post(url, **kwargs):
    kwargs.setdefault("timeout", 15)
    kwargs["proxies"] = {"http": None, "https": None}
    return _ORIG_REQUESTS_POST(url, **kwargs)

requests.get = _no_proxy_get
requests.post = _no_proxy_post

from sqlalchemy.orm import Session

from api.database import DailyBriefingDB, UserLLMConfigDB

logger = logging.getLogger(__name__)

# Limit concurrent HTTP requests to avoid overwhelming data sources
_SEMAPHORE = asyncio.Semaphore(3)


# ─── DB CRUD ─────────────────────────────────────────────────────────────────

def get_briefing(db: Session, user_id: str, date_str: str) -> Optional[dict]:
    row = (
        db.query(DailyBriefingDB)
        .filter(DailyBriefingDB.user_id == user_id, DailyBriefingDB.date == date_str)
        .first()
    )
    return row.to_dict() if row else None


def upsert_briefing(db: Session, user_id: str, date_str: str, data: dict) -> dict:
    row = (
        db.query(DailyBriefingDB)
        .filter(DailyBriefingDB.user_id == user_id, DailyBriefingDB.date == date_str)
        .first()
    )
    if row:
        for k, v in data.items():
            setattr(row, k, v)
    else:
        row = DailyBriefingDB(id=uuid4().hex, user_id=user_id, date=date_str, **data)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


def list_briefings(db: Session, user_id: str, limit: int = 30) -> list[dict]:
    rows = (
        db.query(DailyBriefingDB)
        .filter(DailyBriefingDB.user_id == user_id)
        .order_by(DailyBriefingDB.date.desc())
        .limit(limit)
        .all()
    )
    return [{"id": r.id, "date": r.date, "status": r.status} for r in rows]


# ─── Data Fetchers ───────────────────────────────────────────────────────────


def _fetch_stock_hist(symbol: str, start_date: str, end_date: str) -> "pd.DataFrame | None":
    """Fetch A-share daily K-line via provider chain: akshare → baostock fallback."""
    import io
    import pandas as pd
    from tradingagents.dataflows.interface import route_to_vendor

    # route_to_vendor accepts YYYY-MM-DD format
    start_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
    end_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

    try:
        csv_str = route_to_vendor("get_stock_data", symbol, start_fmt, end_fmt)
        # Parse CSV: skip comment lines starting with #
        lines = [ln for ln in csv_str.split("\n") if not ln.startswith("#") and ln.strip()]
        if not lines:
            return None
        df = pd.read_csv(io.StringIO("\n".join(lines)))
        if df.empty:
            return None
        # Normalize columns to match existing analysis code (Chinese names from akshare)
        col_map = {"Date": "日期", "Open": "开盘", "High": "最高", "Low": "最低",
                    "Close": "收盘", "Volume": "成交量"}
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
        return df
    except Exception:
        return None


def _fetch_stock_news(symbol: str, since_date: str) -> str:
    """Fetch recent stock news via akshare. Returns semicolon-separated titles."""
    try:
        import akshare as ak
        code = symbol.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        ndf = ak.stock_news_em(symbol=code)
        if ndf is None or ndf.empty:
            return ""
        date_col = "发布时间" if "发布时间" in ndf.columns else None
        if date_col:
            import pandas as pd
            ndf[date_col] = pd.to_datetime(ndf[date_col], errors="coerce")
            start_dt = pd.to_datetime(since_date)
            ndf = ndf[ndf[date_col] >= start_dt]
        if ndf.empty:
            return ""
        titles = ndf["新闻标题"].head(3).tolist() if "新闻标题" in ndf.columns else []
        return "；".join(str(t) for t in titles if str(t) != "nan")
    except Exception:
        return ""


def _fetch_stock_hist(symbol: str, start_date: str, end_date: str) -> "pd.DataFrame | None":
    """Fetch A-share daily K-line via provider chain: akshare -> baostock fallback."""
    from tradingagents.dataflows.interface import route_to_vendor

    start_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
    end_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

    try:
        csv_str = route_to_vendor("get_stock_data", symbol, start_fmt, end_fmt)
        lines = [ln for ln in csv_str.splitlines() if not ln.startswith("#") and ln.strip()]
        if not lines:
            return None
        import pandas as pd
        df = pd.read_csv(io.StringIO("\n".join(lines)))
        if df.empty:
            return None
        col_map = {
            "Date": "日期", "Open": "开盘", "High": "最高", "Low": "最低",
            "Close": "收盘", "Volume": "成交量",
        }
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
        return df
    except Exception:
        return None


def _fetch_stock_news(symbol: str, since_date: str) -> str:
    """Fetch recent stock news via akshare. Returns semicolon-separated titles."""
    try:
        import akshare as ak
        import pandas as pd
        code = symbol.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        ndf = ak.stock_news_em(symbol=code)
        if ndf is None or ndf.empty:
            return ""
        date_col = "发布时间" if "发布时间" in ndf.columns else None
        if date_col:
            ndf[date_col] = pd.to_datetime(ndf[date_col], errors="coerce")
            start_dt = pd.to_datetime(since_date)
            ndf = ndf[ndf[date_col] >= start_dt]
        if ndf.empty:
            return ""
        titles = ndf["新闻标题"].head(3).tolist() if "新闻标题" in ndf.columns else []
        return "；".join(str(t) for t in titles if str(t) != "nan")
    except Exception:
        return ""


async def _fetch_overseas_market() -> dict:
    """Fetch overseas market data via EastMoney + Sina (no yfinance dependency)."""
    result = {}

    def _em_indices(fs: str):
        """Query EastMoney push API for index data."""
        r = requests.get(
            "https://push2.eastmoney.com/api/qt/clist/get",
            params={
                "np": 2, "fltt": 1, "invt": 2, "fs": fs,
                "fields": "f12,f14,f2,f3,f4",
                "fid": "f3", "pn": 1, "pz": 20, "po": 1, "dect": 1,
            },
            timeout=10,
        )
        data = r.json()
        items = []
        if data.get("data") and data["data"].get("diff"):
            for v in data["data"]["diff"].values():
                price = (v.get("f2") or 0) / 100
                chg_pct = (v.get("f3") or 0) / 100
                items.append({
                    "name": v.get("f14", ""),
                    "symbol": v.get("f12", ""),
                    "close": round(price, 2),
                    "change_pct": round(chg_pct, 2),
                })
        return items

    # US indices (EastMoney codes: 100.DJIA, 100.SPX, 100.NDX)
    try:
        result["us_indices"] = await asyncio.to_thread(
            _em_indices, "i:100.DJIA,i:100.SPX,i:100.NDX"
        )
    except Exception as e:
        logger.warning(f"US indices fetch failed: {e}")
        result["us_indices"] = []

    # HK indices (100.HSI, 100.HSCEI)
    try:
        result["hk_index"] = await asyncio.to_thread(
            _em_indices, "i:100.HSI,i:100.HSCEI"
        )
    except Exception as e:
        logger.warning(f"HK index fetch failed: {e}")
        result["hk_index"] = []

    # A50 futures — try EastMoney futures codes
    try:
        def _fetch_a50():
            # Try multiple EastMoney futures market codes for SGX A50
            for a50_code in ("i:8.XINA50", "i:8.CN00Y", "i:113.XINA50"):
                a50_items = _em_indices(a50_code)
                if a50_items:
                    item = a50_items[0]
                    item["name"] = "A50期货"
                    return item
            return None
        result["a50_futures"] = await asyncio.to_thread(_fetch_a50)
    except Exception as e:
        logger.warning(f"A50 futures fetch failed: {e}")
        result["a50_futures"] = None

    # Commodities (Sina futures)
    try:
        def _fetch_commodities():
            items = []
            for sym, name in [("hf_GC", "黄金"), ("hf_CL", "原油")]:
                try:
                    req = urllib.request.Request(
                        f"https://hq.sinajs.cn/list={sym}",
                        headers={"Referer": "https://finance.sina.com.cn"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        text = resp.read().decode("gbk", errors="replace")
                    if "=" in text and "," in text:
                        content = text.split("=", 1)[1].strip().strip('"')
                        parts = content.split(",")
                        if len(parts) >= 8:
                            latest = float(parts[0]) if parts[0] else 0
                            prev_close = float(parts[7]) if parts[7] else 0
                            if latest and prev_close:
                                chg_pct = (latest - prev_close) / prev_close * 100
                                items.append({
                                    "name": name,
                                    "symbol": sym,
                                    "close": round(latest, 2),
                                    "change_pct": round(chg_pct, 2),
                                })
                except Exception:
                    pass
            return items
        result["commodities"] = await asyncio.to_thread(_fetch_commodities)
    except Exception as e:
        logger.warning(f"Commodities fetch failed: {e}")
        result["commodities"] = []

    # USD/CNY (try Sina)
    try:
        def _fetch_usdcny():
            req = urllib.request.Request(
                "https://hq.sinajs.cn/list=fx_susdcny",
                headers={"Referer": "https://finance.sina.com.cn"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = resp.read().decode("gbk", errors="replace")
            if "=" in text and "," in text:
                content = text.split("=", 1)[1].strip().strip('"')
                parts = content.split(",")
                # Sina FX format: [0]=time, [1]=latest, [8]=prev_close
                if len(parts) >= 9 and parts[1] and parts[8]:
                    try:
                        latest = float(parts[1])
                        prev_close = float(parts[8])
                        if latest and prev_close:
                            chg_pct = (latest - prev_close) / prev_close * 100
                            return [{
                                "name": "美元/人民币",
                                "symbol": "USDCNY",
                                "close": round(latest, 4),
                                "change_pct": round(chg_pct, 4),
                            }]
                    except (ValueError, TypeError):
                        pass
            return []
        result["fx"] = await asyncio.to_thread(_fetch_usdcny)
    except Exception as e:
        logger.warning(f"USD/CNY fetch failed: {e}")
        result["fx"] = []

    return result


async def _fetch_top_news(curr_date: str) -> list[dict]:
    """Fetch macro news via akshare news_cctv."""
    try:
        import akshare as ak

        def _get():
            def _try_news(date_str: str):
                try:
                    return ak.news_cctv(date=date_str)
                except Exception:
                    return None

            target = curr_date.replace("-", "")
            df = _try_news(target)
            if df is None or df.empty:
                for back in range(1, 4):
                    probe_dt = datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=back)
                    probe = probe_dt.strftime("%Y%m%d")
                    probe_df = _try_news(probe)
                    if probe_df is not None and not probe_df.empty:
                        return probe_df
                return None
            return df

        df = await asyncio.to_thread(_get)
        if df is None:
            return []

        items = []
        for _, row in df.head(15).iterrows():
            title = str(row.get("title", row.get("标题", "")))
            content = str(row.get("content", row.get("内容", "")))
            if not title:
                continue
            items.append({
                "title": title,
                "content_preview": content[:200] if content and content != "nan" else "",
                "source": "CCTV",
            })
        return items
    except Exception:
        return []


async def _fetch_fund_flow_summary() -> Optional[dict]:
    """Fetch market fund flow via EastMoney API directly."""
    try:
        def _get():
            url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
            params = {
                "lmt": 0, "klt": 101,
                "secid": "1.000001", "secid2": "0.399001",
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
                "ut": "b2884a393a59ad64002292a3e90d46a5",
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            data = r.json()
            if data.get("data") and data["data"].get("klines"):
                last = data["data"]["klines"][-1]
                parts = last.split(",")
                if len(parts) >= 6:
                    return {
                        "date": parts[0],
                        "main_net": float(parts[1]) if parts[1] else 0,
                        "super_large_net": float(parts[4]) if parts[4] else 0,
                        "large_net": float(parts[5]) if parts[5] else 0,
                    }
            return None
        return await asyncio.to_thread(_get)
    except Exception:
        return None


async def _analyze_watchlist(db: Session, user_id: str, prev_trade_date: str) -> list[dict]:
    """Analyze each watchlist stock: news + price change + simple signals."""
    from api.services.watchlist_service import list_watchlist

    items = list_watchlist(db, user_id)
    if not items:
        return []

    # Resolve stock names from the pre-loaded stock map cache
    stock_name_map = {}
    try:
        from api.main import _get_reverse_stock_map_cached_only
        stock_name_map = _get_reverse_stock_map_cached_only()
    except Exception:
        pass

    async def _analyze_one(wl: dict) -> dict:
        symbol = wl["symbol"]
        name = stock_name_map.get(symbol, "") or wl.get("name", "") or symbol
        notes = wl.get("notes", "")
        result = {
            "symbol": symbol,
            "name": name,
            "notes": notes,
            "latest_price": None,
            "change_pct": None,
            "news_summary": "",
            "signals": [],
            "decision_line": None,
            "bull_line": None,
            "orbit_line": None,
            "orbit_direction": 0,
        }
        try:
            end = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
            df = _fetch_stock_hist(symbol, start, end)
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                result["latest_price"] = round(float(latest["收盘"]), 2)
                if len(df) >= 2:
                    prev = df.iloc[-2]
                    result["change_pct"] = round(
                        (float(latest["收盘"]) - float(prev["收盘"])) / float(prev["收盘"]) * 100, 2
                    )

                # Compute niuxiong indicators
                if len(df) >= 60:
                    try:
                        from tradingagents.indicators.niuxiong_line import calculate_niuxiong_line
                        eng_df = df.rename(columns={"开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"})
                        nx = calculate_niuxiong_line(eng_df)
                        latest_nx = nx.iloc[-1]
                        result["decision_line"] = round(float(latest_nx.get("decision_line", 0)), 2)
                        result["bull_line"] = round(float(latest_nx.get("bull_line", 0)), 2)
                        result["orbit_line"] = round(float(latest_nx.get("orbit_line", 0)), 2)
                        result["orbit_direction"] = int(latest_nx.get("orbit_direction", 0))

                        # Build signals from niuxiong indicators
                        if latest_nx.get("buy_signal"):
                            result["signals"].append({"name": "牛熊线买入", "interpretation": "强多"})
                        if latest_nx.get("sell_signal"):
                            result["signals"].append({"name": "牛熊线卖出", "interpretation": "强空"})
                        if latest_nx.get("bullish_alignment"):
                            result["signals"].append({"name": "多头排列", "interpretation": "偏多"})
                        if latest_nx.get("bearish_alignment"):
                            result["signals"].append({"name": "空头排列", "interpretation": "偏空"})

                        # Price vs key levels
                        if result["latest_price"] and result["decision_line"]:
                            if result["latest_price"] > result["decision_line"]:
                                result["signals"].append({"name": "站上决策线", "value": f"{result['decision_line']:.2f}", "interpretation": "偏多"})
                            else:
                                result["signals"].append({"name": "跌破决策线", "value": f"{result['decision_line']:.2f}", "interpretation": "偏空"})
                    except Exception as e:
                        logger.warning(f"Niuxiong computation failed for {symbol}: {e}")

            # News
            try:
                result["news_summary"] = await asyncio.to_thread(_fetch_stock_news, symbol, prev_trade_date)
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Watchlist analysis failed for {symbol}: {e}")

        return result

    async def _analyze_one_throttled(wl: dict) -> dict:
        async with _SEMAPHORE:
            return await _analyze_one(wl)

    tasks = [_analyze_one_throttled(wl) for wl in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


async def _analyze_portfolio(db: Session, user_id: str, prev_trade_date: str) -> list[dict]:
    """Analyze each portfolio position: P&L + risk signals."""
    from api.services.portfolio_import_service import list_imported_positions

    positions = list_imported_positions(db, user_id)
    if not positions:
        return []

    active = [p for p in positions if (p.get("current_position") or 0) > 0]
    if not active:
        return []

    # Resolve stock names from the pre-loaded stock map cache
    stock_name_map = {}
    try:
        from api.main import _get_reverse_stock_map_cached_only
        stock_name_map = _get_reverse_stock_map_cached_only()
    except Exception:
        pass

    async def _analyze_one(pos: dict) -> dict:
        symbol = pos["symbol"]
        name = pos.get("name") or stock_name_map.get(symbol, "") or symbol
        avg_cost = float(pos.get("average_cost") or 0)
        position = float(pos.get("current_position") or 0)
        result = {
            "symbol": symbol,
            "name": name,
            "position": position,
            "avg_cost": round(avg_cost, 2),
            "current_price": None,
            "market_value": float(pos.get("market_value") or 0),
            "pnl": None,
            "pnl_pct": None,
            "risk_signals": [],
            "decision_line": None,
            "bull_line": None,
            "orbit_line": None,
            "orbit_direction": 0,
        }

        # If no cost basis, skip price fetch
        if avg_cost <= 0:
            return result

        try:
            end = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
            df = _fetch_stock_hist(symbol, start, end)
            if df is not None and not df.empty:
                latest_close = float(df.iloc[-1]["收盘"])
                result["current_price"] = round(latest_close, 2)
                pnl = (latest_close - avg_cost) * position
                pnl_pct = (latest_close - avg_cost) / avg_cost * 100
                result["pnl"] = round(pnl, 2)
                result["pnl_pct"] = round(pnl_pct, 2)

                # Risk signals
                if pnl_pct > 50:
                    result["risk_signals"].append("盈利超50%，注意高位回撤")
                if pnl_pct < -15:
                    result["risk_signals"].append("亏损超15%，关注止损")

                # Niuxiong indicators for support/resistance reference
                if len(df) >= 60:
                    try:
                        from tradingagents.indicators.niuxiong_line import calculate_niuxiong_line
                        eng_df = df.rename(columns={"开盘": "open", "最高": "high", "最低": "low", "收盘": "close", "成交量": "volume"})
                        nx = calculate_niuxiong_line(eng_df)
                        latest_nx = nx.iloc[-1]
                        result["decision_line"] = round(float(latest_nx.get("decision_line", 0)), 2)
                        result["bull_line"] = round(float(latest_nx.get("bull_line", 0)), 2)
                        result["orbit_line"] = round(float(latest_nx.get("orbit_line", 0)), 2)
                        result["orbit_direction"] = int(latest_nx.get("orbit_direction", 0))

                        if latest_nx.get("buy_signal"):
                            result["risk_signals"].append("牛熊线买入信号")
                        if latest_nx.get("sell_signal"):
                            result["risk_signals"].append("牛熊线卖出信号，注意风险")
                        if latest_nx.get("bearish_alignment"):
                            result["risk_signals"].append("空头排列，趋势走弱")
                        if pnl_pct < 0 and latest_nx.get("bearish_alignment"):
                            result["risk_signals"].append("亏损股处于空头排列，建议评估止损")
                    except Exception as e:
                        logger.warning(f"Niuxiong computation failed for {symbol}: {e}")

        except Exception as e:
            logger.warning(f"Portfolio analysis failed for {symbol}: {e}")

        return result

    async def _analyze_one_throttled(pos: dict) -> dict:
        async with _SEMAPHORE:
            return await _analyze_one(pos)

    tasks = [_analyze_one_throttled(p) for p in active]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


# ─── LLM Synthesis ───────────────────────────────────────────────────────────

async def _generate_trading_advice(
    market_data: dict,
    top_news: list,
    watchlist_analysis: list,
    portfolio_analysis: list,
    user_id: str,
    db: Session,
) -> dict:
    """Call LLM to synthesize trading advice from all data sections."""

    # Build text summaries for LLM context
    market_lines = []
    if market_data.get("us_indices"):
        market_lines.append("美股：")
        for idx in market_data["us_indices"]:
            market_lines.append(f"  {idx['name']}: {idx['close']} ({idx['change_pct']:+.2f}%)")
    if market_data.get("hk_index"):
        for idx in market_data["hk_index"]:
            market_lines.append(f"港股{idx['name']}: {idx['close']} ({idx['change_pct']:+.2f}%)")
    if market_data.get("a50_futures"):
        a50 = market_data["a50_futures"]
        market_lines.append(f"A50期货: {a50['close']} ({a50['change_pct']:+.2f}%)")
    if market_data.get("commodities"):
        market_lines.append("商品：")
        for c in market_data["commodities"]:
            market_lines.append(f"  {c['name']}: {c['close']} ({c['change_pct']:+.2f}%)")
    market_summary = "\n".join(market_lines) if market_lines else "暂无海外市场数据"

    news_lines = []
    for n in top_news[:10]:
        news_lines.append(f"- {n['title']}")
    news_summary = "\n".join(news_lines) if news_lines else "暂无重大要闻"

    wl_lines = []
    for w in watchlist_analysis:
        signals_str = ", ".join(s["name"] for s in w.get("signals", []))
        dl = w.get("decision_line")
        bl = w.get("bull_line")
        ol = w.get("orbit_line")
        od = w.get("orbit_direction", 0)
        levels = []
        if dl: levels.append(f"决策线{dl:.2f}")
        if bl: levels.append(f"牛线{bl:.2f}")
        if ol: levels.append(f"轨道线{ol:.2f}({'多头' if od > 0 else '空头' if od < 0 else '无方向'})")
        wl_lines.append(
            f"{w['symbol']} {w['name']}: "
            f"现价{w.get('latest_price', 'N/A')} "
            f"涨跌{w.get('change_pct', 'N/A')}% "
            f"指标: {'; '.join(levels) if levels else '无'} "
            f"信号: {signals_str or '无'} "
            f"消息: {w.get('news_summary', '')[:80]}"
        )
    watchlist_summary = "\n".join(wl_lines) if wl_lines else "暂无自选股"

    pf_lines = []
    for p in portfolio_analysis:
        dl = p.get("decision_line")
        bl = p.get("bull_line")
        ol = p.get("orbit_line")
        od = p.get("orbit_direction", 0)
        levels = []
        if dl: levels.append(f"决策线{dl:.2f}")
        if ol: levels.append(f"轨道线{ol:.2f}({'多头' if od > 0 else '空头'})")
        pf_lines.append(
            f"{p['symbol']} {p['name']}: "
            f"成本{p['avg_cost']} 现价{p.get('current_price', 'N/A')} "
            f"盈亏{p.get('pnl_pct', 'N/A')}% "
            f"关键位: {'; '.join(levels) if levels else '无'} "
            f"信号: {', '.join(p.get('risk_signals', [])) or '无'}"
        )
    portfolio_summary = "\n".join(pf_lines) if pf_lines else "暂无持仓"

    # Build date string for the trading plan title
    today_str = datetime.now(timezone.utc).strftime("%m月%d日")

    # Build prompt
    prompt = f"""你是一位资深A股短线交易员，请根据以下盘前数据，生成一份可执行的交易计划。

【海外市场表现】
{market_summary}

【重大宏观要闻】
{news_summary}

【自选股数据】
{watchlist_summary}

【持仓股数据】
{portfolio_summary}

请生成今日盘前交易计划，标题为"【{today_str} 盘前交易计划】"。严格按照以下JSON格式输出，不要添加markdown代码块：

{{
  "情绪与主线": "一句话概括今日大盘预判情绪和主线方向。格式：大盘预计放量/缩量震荡/上涨/下跌，今日主线看好XXX",
  "自选股观察": [
    {{
      "股票": "代码+名称",
      "策略类型": "趋势回踩/底部半路/突破确认/消息驱动",
      "入场条件": "具体的入场条件，如：若缩量回调至10日线(XX元)附近企稳，买入1层仓",
      "理由": "一句话说明为什么关注"
    }}
  ],
  "持仓处理": [
    {{
      "股票": "代码+名称",
      "盈亏": "+X%或-Y%",
      "止盈条件": "具体止盈策略，如：冲高不封板则在涨幅3%-5%分批止盈",
      "止损条件": "具体止损策略，如：跌破XX元(昨日低点)无条件清仓",
      "建议": "持有/减仓/加仓"
    }}
  ]
}}

规则：
1. 自选股观察必须覆盖所有自选股，每只都要给出具体策略、入场条件和仓位层数
2. 持仓处理覆盖所有持仓股，给出明确的止盈止损价位
3. 入场价位优先参考"轨道线"（动态支撑/阻力），趋势方向参考"决策线"与"牛线"排列，回踩买点看轨道线附近企稳，突破买点看价格站上轨道线
4. 止损位优先参考：轨道线下方2%、成本价、或决策线破位，任选一个最合适的
5. 价位必须根据现价和指标数据推算，不要编造数字
6. 大盘情绪结合海外市场、A50期货和宏观新闻判断"""

    # Get LLM config from default config + user DB override
    from tradingagents.default_config import DEFAULT_CONFIG
    provider = DEFAULT_CONFIG["llm_provider"]
    model = DEFAULT_CONFIG["quick_think_llm"]
    base_url = DEFAULT_CONFIG["backend_url"]
    api_key = DEFAULT_CONFIG["api_key"]

    llm_config = db.query(UserLLMConfigDB).filter(UserLLMConfigDB.user_id == user_id).first()
    if llm_config:
        provider = llm_config.llm_provider or provider
        model = llm_config.quick_think_llm or llm_config.deep_think_llm or model
        base_url = llm_config.backend_url or base_url
        if llm_config.api_key_encrypted:
            from api.services.auth_service import decrypt_secret
            db_api_key = decrypt_secret(llm_config.api_key_encrypted)
            if db_api_key:
                api_key = db_api_key

    # Map provider values to what create_llm_client expects
    provider_map = {"deepseek": "openai", "zhipu": "openai", "moonshot": "openai"}
    mapped_provider = provider_map.get(provider.lower(), provider.lower())

    try:
        from tradingagents.llm_clients.factory import create_llm_client

        client = create_llm_client(provider=mapped_provider, model=model, base_url=base_url, api_key=api_key)
        llm = client.get_llm()
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Extract JSON from response
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        advice = json.loads(content)
        return {
            "sentiment": advice.get("情绪与主线", advice.get("sentiment", "")),
            "watchlist_plan": advice.get("自选股观察", advice.get("watchlist_plan", [])),
            "portfolio_plan": advice.get("持仓处理", advice.get("portfolio_plan", [])),
        }
    except Exception as e:
        logger.error(f"LLM trading advice generation failed: {e}")
        return {
            "sentiment": "AI建议生成失败，请参考其他板块数据",
            "watchlist_plan": [],
            "portfolio_plan": [],
            "error": str(e),
        }


# ─── Main Orchestration ──────────────────────────────────────────────────────

async def generate_briefing(db: Session, user_id: str, date_str: str, force: bool = False) -> dict:
    """Generate or return a pre-market briefing for the given date."""

    # Check existing
    existing = get_briefing(db, user_id, date_str)
    if existing and existing.get("status") == "completed" and not force:
        return existing

    # Determine previous trading day
    from tradingagents.dataflows.trade_calendar import previous_cn_trading_day
    prev_trade_date = previous_cn_trading_day(date_str)

    # Mark as running
    upsert_briefing(db, user_id, date_str, {"status": "running"})

    try:
        # Phase 1: Fetch market data + news in parallel
        market_task = _fetch_overseas_market()
        fund_task = _fetch_fund_flow_summary()
        news_task = _fetch_top_news(date_str)

        market_data, fund_flow, top_news = await asyncio.gather(
            market_task, fund_task, news_task, return_exceptions=True,
        )

        if isinstance(market_data, Exception):
            market_data = {"error": str(market_data)}
        if isinstance(fund_flow, Exception):
            fund_flow = None
        if isinstance(top_news, Exception):
            top_news = []

        market_data["fund_flow"] = fund_flow

        # Phase 2: Watchlist + Portfolio analysis in parallel
        wl_task = _analyze_watchlist(db, user_id, prev_trade_date)
        pf_task = _analyze_portfolio(db, user_id, prev_trade_date)
        watchlist_analysis, portfolio_analysis = await asyncio.gather(
            wl_task, pf_task, return_exceptions=True,
        )
        if isinstance(watchlist_analysis, Exception):
            watchlist_analysis = []
        if isinstance(portfolio_analysis, Exception):
            portfolio_analysis = []

        # Phase 3: LLM trading advice
        trading_advice = await _generate_trading_advice(
            market_data, top_news, watchlist_analysis, portfolio_analysis, user_id, db,
        )

        # Store
        result = upsert_briefing(db, user_id, date_str, {
            "status": "completed",
            "market_data": market_data,
            "top_news": top_news,
            "watchlist_analysis": watchlist_analysis,
            "portfolio_analysis": portfolio_analysis,
            "trading_advice": trading_advice,
            "generated_at": datetime.now(timezone.utc),
            "error": None,
        })
        return result

    except Exception as e:
        logger.exception(f"Briefing generation failed for {date_str}: {e}")
        upsert_briefing(db, user_id, date_str, {
            "status": "failed",
            "error": str(e),
        })
        raise
