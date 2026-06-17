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


async def _fetch_a50_futures_v2() -> Optional[dict]:
    """Fetch A50 futures via EastMoney futsseapi (SGX exchange)."""
    try:
        def _get():
            for page in range(4):  # 622 items across ~2 pages of 500
                r = requests.get(
                    "https://futsseapi.eastmoney.com/list/COMEX,NYMEX,COBOT,SGX,NYBOT,LME,MDEX,TOCOM,IPE",
                    params={
                        "orderBy": "dm", "sort": "desc", "pageSize": "500", "pageIndex": str(page),
                        "token": "58b2fa8f54638b60b87d69b31969089c",
                        "field": "dm,sc,name,p,zsjd,zde,zdf,f152,o,h,l,zjsj,vol,wp,np,ccl",
                        "blockName": "callback",
                    },
                    timeout=15,
                )
                data = r.json()
                items = data.get("list", [])
                for item in items:
                    if item.get("dm") == "CN00Y":
                        price = item.get("p")
                        chg_pct = item.get("zdf")
                        if price and price != "-" and chg_pct is not None and chg_pct != "-":
                            prev_settle = item.get("zsjd")
                            open_p = float(item.get("o")) if item.get("o") and item["o"] != "-" else 0
                            high_p = float(item.get("h")) if item.get("h") and item["h"] != "-" else 0
                            low_p = float(item.get("l")) if item.get("l") and item["l"] != "-" else 0
                            return {
                                "name": "A50期货",
                                "symbol": "CN00Y",
                                "close": round(float(price), 2),
                                "change_pct": round(float(chg_pct), 2),
                                "high": high_p,
                                "low": low_p,
                                "open": open_p,
                            }
                if len(items) < 500:
                    break
            return None
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"A50 futures v2 fetch failed: {e}")
        return None


async def _fetch_chinese_adrs() -> list[dict]:
    """Fetch key Chinese ADR stocks via Sina US API."""
    adr_symbols = {
        "BABA": "阿里巴巴", "JD": "京东", "BIDU": "百度", "PDD": "拼多多",
        "NIO": "蔚来", "XPEV": "小鹏汽车", "LI": "理想汽车",
        "BILI": "哔哩哔哩", "TME": "腾讯音乐", "BEKE": "贝壳",
        "NTES": "网易", "BZ": "BOSS直聘", "YUMC": "百胜中国",
    }

    def _get():
        results = []
        codes = ",".join(f"gb_{s.lower()}" for s in adr_symbols)
        try:
            req = urllib.request.Request(
                f"https://hq.sinajs.cn/list={codes}",
                headers={"Referer": "https://finance.sina.com.cn"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("gbk", errors="replace")

            for line in text.strip().split("\n"):
                if "=" not in line or "," not in line:
                    continue
                sym = line.split("=")[0].replace("var hq_str_gb_", "").upper()
                content = line.split("=", 1)[1].strip().strip('"')
                parts = content.split(",")
                if len(parts) < 5 or not parts[1]:
                    continue
                name = adr_symbols.get(sym, parts[0])
                price = float(parts[1])
                chg_pct = float(parts[2]) if parts[2] else 0
                chg_amt = float(parts[4]) if len(parts) > 4 and parts[4] else 0
                results.append({
                    "symbol": sym,
                    "name": name,
                    "close": round(price, 2),
                    "change_pct": round(chg_pct, 2),
                    "change_amt": round(chg_amt, 2),
                })
        except Exception as e:
            logger.warning(f"Chinese ADR fetch failed: {e}")
        return results

    return await asyncio.to_thread(_get)


async def _fetch_market_sentiment(curr_date: str) -> Optional[dict]:
    """Fetch A-share market sentiment: limit-up/down counts, bust rate, volume comparison."""
    try:
        import akshare as ak

        def _get():
            date_str = curr_date.replace("-", "")
            result = {"limit_up_count": 0, "limit_down_count": 0, "bust_rate_pct": 0,
                       "max_streak": 0, "top_streak_stocks": [], "prev_volume": None, "volume_change_pct": None}

            # Limit-up pool
            try:
                zt_df = ak.stock_zt_pool_em(date=date_str)
                if zt_df is not None and not zt_df.empty:
                    result["limit_up_count"] = len(zt_df)
                    # Column names: 代码/名称/涨跌幅/最新价/炸板次数/涨停统计/连板数/所属行业
                    bust_col = "炸板次数" if "炸板次数" in zt_df.columns else None
                    if bust_col:
                        bust_cnt = (zt_df[bust_col] > 0).sum()
                        result["bust_rate_pct"] = round(int(bust_cnt) / len(zt_df) * 100, 1) if len(zt_df) > 0 else 0
                    streak_col = "连板数" if "连板数" in zt_df.columns else None
                    if streak_col:
                        top = zt_df.nlargest(5, streak_col)
                        result["max_streak"] = int(top[streak_col].max()) if not top.empty else 0
                        code_col = "代码" if "代码" in zt_df.columns else "股票代码"
                        name_col = "名称" if "名称" in zt_df.columns else "股票名称"
                        industry_col = "所属行业" if "所属行业" in zt_df.columns else "涨停原因"
                        # Optional detail columns: 封单资金(万), 首次封板时间, 最后封板时间
                        seal_col = "封板资金" if "封板资金" in zt_df.columns else None
                        first_col = "首次封板时间" if "首次封板时间" in zt_df.columns else None
                        last_col = "最后封板时间" if "最后封板时间" in zt_df.columns else None
                        bust_col2 = "炸板次数" if "炸板次数" in zt_df.columns else None
                        cng_col = "涨跌幅" if "涨跌幅" in zt_df.columns else None
                        result["top_streak_stocks"] = []
                        for _, r in top.iterrows():
                            if not r.get(streak_col) or r[streak_col] <= 0:
                                continue
                            stock = {
                                "name": str(r.get(name_col, "")),
                                "code": str(r.get(code_col, "")),
                                "streak": int(r[streak_col]),
                                "reason": str(r.get(industry_col, "")),
                            }
                            if seal_col and r.get(seal_col) is not None:
                                stock["seal_amount_wan"] = round(float(r[seal_col]) / 10000, 1) if float(r[seal_col]) > 10000 else round(float(r[seal_col]), 1)
                            if first_col and r.get(first_col) and str(r[first_col]) != "nan":
                                stock["first_seal_time"] = str(r[first_col])
                            if last_col and r.get(last_col) and str(r[last_col]) != "nan":
                                stock["last_seal_time"] = str(r[last_col])
                            if bust_col2 and r.get(bust_col2) is not None:
                                stock["bust_count"] = int(r[bust_col2])
                            if cng_col and r.get(cng_col) is not None:
                                stock["change_pct"] = round(float(r[cng_col]), 2)
                            result["top_streak_stocks"].append(stock)
            except Exception as e:
                logger.warning(f"Limit-up pool fetch failed: {e}")

            # Limit-down pool
            try:
                dt_df = ak.stock_zt_pool_dtgc_em(date=date_str)
                if dt_df is not None and not dt_df.empty:
                    result["limit_down_count"] = len(dt_df)
            except Exception as e:
                logger.warning(f"Limit-down pool fetch failed: {e}")

            # Volume comparison via Shanghai index (direct push2 API)
            try:
                r = requests.get(
                    "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                    params={
                        "secid": "1.000001", "klt": 101, "lmt": 5,
                        "fields1": "f1,f2,f3,f4,f5,f6",
                        "fields2": "f51,f52,f53,f54,f55,f56,f57",
                    },
                    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
                    timeout=15,
                )
                d = r.json()
                klines = d.get("data", {}).get("klines", [])
                if klines and len(klines) >= 2:
                    # kline format: date,open,close,high,low,volume,amount
                    prev_parts = klines[-2].split(",")
                    curr_parts = klines[-1].split(",")
                    if len(prev_parts) >= 6 and len(curr_parts) >= 6:
                        prev_vol = float(prev_parts[5]) if prev_parts[5] != "-" else 0
                        curr_vol = float(curr_parts[5]) if curr_parts[5] != "-" else 0
                        if prev_vol > 0:
                            result["prev_volume"] = round(prev_vol, 0)
                            result["volume_change_pct"] = round((curr_vol - prev_vol) / prev_vol * 100, 2)
            except Exception as e:
                logger.warning(f"Volume comparison fetch failed: {e}")

            return result
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"Market sentiment fetch failed: {e}")
        return None


async def _fetch_north_bound() -> Optional[dict]:
    """Fetch north-bound capital flow (沪股通+深股通)."""
    try:
        import akshare as ak

        def _get():
            result = {"hgt_net": None, "sgt_net": None, "total_net": None, "recent_days": []}
            try:
                hgt = ak.stock_hsgt_hist_em(symbol="沪股通")
                if hgt is not None and not hgt.empty:
                    latest = hgt.iloc[-1]
                    hgt_val = float(latest.get("净流入", 0))
                    result["hgt_net"] = round(hgt_val / 1e8, 2)
                    for _, row in hgt.tail(5).iterrows():
                        result["recent_days"].append({
                            "date": str(row.get("日期", "")),
                            "net_flow_yi": round(float(row.get("净流入", 0)) / 1e8, 2),
                        })
            except Exception:
                pass

            try:
                sgt = ak.stock_hsgt_hist_em(symbol="深股通")
                if sgt is not None and not sgt.empty:
                    sgt_val = float(sgt.iloc[-1].get("净流入", 0))
                    result["sgt_net"] = round(sgt_val / 1e8, 2)
            except Exception:
                pass

            if result["hgt_net"] is not None and result["sgt_net"] is not None:
                result["total_net"] = round(result["hgt_net"] + result["sgt_net"], 2)
            # If all values are zero, data is not available (exchanges stopped publishing since 2024-08)
            if result.get("total_net") == 0.0 and result.get("hgt_net") == 0.0 and result.get("sgt_net") == 0.0:
                return None
            return result
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"North-bound fetch failed: {e}")
        return None


async def _fetch_dragon_tiger(curr_date: str) -> Optional[dict]:
    """Fetch daily dragon tiger board summary (全市场龙虎榜)."""
    try:
        import akshare as ak

        def _get():
            result = {"total_records": 0, "top_net_buy": [], "top_net_sell": [], "institution_net": None}
            try:
                # Use LHB institution stats for aggregate view
                jg_df = ak.stock_lhb_jgmmtj_em(start_date=curr_date.replace("-", ""), end_date=curr_date.replace("-", ""))
                if jg_df is not None and not jg_df.empty:
                    total_buy = 0
                    total_sell = 0
                    for _, row in jg_df.iterrows():
                        total_buy += float(row.get("买入额", 0) or 0)
                        total_sell += float(row.get("卖出额", 0) or 0)
                    result["institution_net"] = round((total_buy - total_sell) / 1e8, 2)
            except Exception:
                pass

            # Get top net buy stocks from LHB detail
            try:
                detail_df = ak.stock_lhb_detail_em(start_date=curr_date.replace("-", ""), end_date=curr_date.replace("-", ""))
                if detail_df is not None and not detail_df.empty:
                    code_col = "代码" if "代码" in detail_df.columns else "股票代码"
                    name_col = "名称" if "名称" in detail_df.columns else "股票名称"
                    buy_col = "买方金额" if "买方金额" in detail_df.columns else "买入额"
                    sell_col = "卖方金额" if "卖方金额" in detail_df.columns else "卖出额"
                    result["total_records"] = len(detail_df[code_col].unique())
                    if buy_col in detail_df.columns and sell_col in detail_df.columns:
                        detail_df[buy_col] = detail_df[buy_col].astype(float)
                        detail_df[sell_col] = detail_df[sell_col].astype(float)
                        detail_df["净买额"] = detail_df[buy_col] - detail_df[sell_col]
                        stock_agg = detail_df.groupby([code_col, name_col]).agg({"净买额": "sum", buy_col: "sum", sell_col: "sum"}).reset_index()
                        top_buy = stock_agg.nlargest(10, "净买额")
                        result["top_net_buy"] = [
                            {"code": r[code_col], "name": r[name_col],
                             "net_buy_wan": round(r["净买额"] / 10000, 1),
                             "buy_wan": round(r[buy_col] / 10000, 1),
                             "sell_wan": round(r[sell_col] / 10000, 1)}
                            for _, r in top_buy.iterrows()
                        ]
                        top_sell = stock_agg.nsmallest(10, "净买额")
                        result["top_net_sell"] = [
                            {"code": r[code_col], "name": r[name_col],
                             "net_buy_wan": round(r["净买额"] / 10000, 1),
                             "buy_wan": round(r[buy_col] / 10000, 1),
                             "sell_wan": round(r[sell_col] / 10000, 1)}
                            for _, r in top_sell.iterrows()
                        ]
            except Exception:
                pass

            return result
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"Dragon tiger fetch failed: {e}")
        return None


async def _fetch_industry_ranking() -> Optional[dict]:
    """Fetch industry sector ranking via EastMoney push2 API (using urllib for better proxy bypass)."""
    try:
        import time as _time
        import urllib.request
        import urllib.parse
        import ssl

        def _get():
            last_err = None
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            for attempt in range(3):
                try:
                    params = urllib.parse.urlencode({
                        "pn": "1", "pz": "100", "po": "1", "np": "1",
                        "fltt": "1", "invt": "2", "dect": "1",
                        "fs": "m:90+t:2",
                        "fields": "f2,f3,f4,f12,f14,f104,f105,f140,f136",
                        "fid": "f3",
                    })
                    url = f"https://push2.eastmoney.com/api/qt/clist/get?{params}"
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
                    )
                    with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
                        d = json.loads(resp.read().decode())
                    items = d.get("data", {}).get("diff", [])
                    if items:
                        rows = []
                        for item in items:
                            rows.append({
                                "name": item.get("f14", ""),
                                "change_pct": round((item.get("f3") or 0) / 100, 2),
                                "code": item.get("f12", ""),
                                "up_count": item.get("f104", 0),
                                "down_count": item.get("f105", 0),
                                "leader": item.get("f140", ""),
                                "leader_change": round((item.get("f136") or 0) / 100, 2) if item.get("f136") else 0,
                            })
                        return {"top": rows[:10], "bottom": rows[-10:], "total": len(rows)}
                except Exception as e:
                    last_err = e
                    _time.sleep(1.5)
            logger.warning(f"Industry ranking failed after 3 attempts: {last_err}")
            return None
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"Industry ranking fetch failed: {e}")
        return None


async def _fetch_sector_fund_flow() -> Optional[dict]:
    """Fetch sector-level fund flow ranking via EastMoney push2 (using urllib to bypass proxy)."""
    try:
        import urllib.request
        import urllib.parse
        import ssl
        import time as _time

        def _get():
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            for attempt in range(3):
                try:
                    params = urllib.parse.urlencode({
                        "pn": "1", "pz": "100", "po": "1", "np": "1",
                        "fltt": "1", "invt": "2", "dect": "1",
                        "fs": "m:90+t:2",
                        "fid": "f62",  # 主力净流入
                        "fields": "f2,f3,f4,f12,f14,f62,f66,f69,f72,f75,f78,f81,f84,f87,f184",
                    })
                    url = f"https://push2.eastmoney.com/api/qt/clist/get?{params}"
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"},
                    )
                    with urllib.request.urlopen(req, timeout=20, context=ssl_ctx) as resp:
                        d = json.loads(resp.read().decode())
                    items = d.get("data", {}).get("diff", [])
                    if not items:
                        return None
                    rows = []
                    for item in items:
                        name = item.get("f14", "")
                        inflow = (item.get("f62") or 0) / 1e8  # 主力净流入(元→亿)
                        rows.append({"name": name, "net_inflow_yi": round(float(inflow), 2)})
                    rows.sort(key=lambda x: x["net_inflow_yi"], reverse=True)
                    return {
                        "top_inflow": rows[:10],
                        "top_outflow": rows[-10:],
                    }
                except Exception as e:
                    if attempt < 2:
                        _time.sleep(1.5)
                        continue
                    logger.warning(f"Sector fund flow fetch failed after 3 attempts: {e}")
                    return None
            return None
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"Sector fund flow fetch error: {e}")
        return None


async def _fetch_stock_announcements(curr_date: str) -> Optional[dict]:
    """Fetch major stock announcements for the day: 重大事项, 业绩预告, 减持."""
    try:
        import akshare as ak

        def _get():
            date_str = curr_date.replace("-", "")
            result = {"major_events": [], "earnings": [], "shareholder_changes": []}

            # 重大事项 (major events)
            try:
                df = ak.stock_notice_report(symbol="重大事项", date=date_str)
                if df is not None and not df.empty:
                    name_col = "名称" if "名称" in df.columns else "股票简称" if "股票简称" in df.columns else df.columns[1]
                    code_col = "代码" if "代码" in df.columns else "股票代码" if "股票代码" in df.columns else df.columns[0]
                    title_col = "公告标题" if "公告标题" in df.columns else "标题" if "标题" in df.columns else df.columns[2]
                    for _, r in df.head(30).iterrows():
                        result["major_events"].append({
                            "code": str(r[code_col]),
                            "name": str(r[name_col]),
                            "title": str(r[title_col]),
                        })
            except Exception as e:
                logger.warning(f"Major events fetch failed: {e}")

            # 减持公告 (shareholder reduction)
            try:
                df2 = ak.stock_notice_report(symbol="持股变动", date=date_str)
                if df2 is not None and not df2.empty:
                    name_col = "名称" if "名称" in df2.columns else "股票简称" if "股票简称" in df2.columns else df2.columns[1]
                    code_col = "代码" if "代码" in df2.columns else "股票代码" if "股票代码" in df2.columns else df2.columns[0]
                    title_col = "公告标题" if "公告标题" in df2.columns else "标题" if "标题" in df2.columns else df2.columns[2]
                    for _, r in df2.head(20).iterrows():
                        result["shareholder_changes"].append({
                            "code": str(r[code_col]),
                            "name": str(r[name_col]),
                            "title": str(r[title_col]),
                        })
            except Exception as e:
                logger.warning(f"Shareholder changes fetch failed: {e}")

            return result if (result["major_events"] or result["shareholder_changes"]) else None
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"Stock announcements fetch failed: {e}")
        return None


async def _fetch_hot_stocks() -> list[dict]:
    """Fetch today's hot stocks with reason tags via 同花顺."""
    try:
        def _get():
            url = "http://zx.10jqka.com.cn/event/api/getharden/date/{}/orderby/date/orderway/desc/charset/GBK/".format(
                datetime.now().strftime("%Y-%m-%d")
            )
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36",
            }
            r = requests.get(url, headers=headers, timeout=10)
            data = r.json()
            if data.get("errocode", 0) != 0:
                return []
            rows = data.get("data") or []
            results = []
            for row in rows[:30]:
                results.append({
                    "code": row.get("code", ""),
                    "name": row.get("name", ""),
                    "change_pct": round(float(row.get("zhangfu", 0)), 2),
                    "turnover": round(float(row.get("huanshou", 0)), 2),
                    "reason": row.get("reason", ""),
                    "amount": row.get("chengjiaoe", 0),
                })
            return results
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"Hot stocks fetch failed: {e}")
        return []


async def _fetch_global_news_fast() -> list[dict]:
    """Fetch 7x24 global financial news via EastMoney."""
    try:
        def _get():
            url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
            params = {
                "client": "web", "biz": "web_724",
                "fastColumn": "102", "sortEnd": "",
                "pageSize": "30",
                "req_trace": str(uuid4()),
            }
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://kuaixun.eastmoney.com/"}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            d = r.json()
            rows = []
            for item in d.get("data", {}).get("fastNewsList", []):
                title = item.get("title", "")
                if not title:
                    continue
                rows.append({
                    "title": title,
                    "summary": (item.get("summary") or "")[:150],
                    "time": item.get("showTime", ""),
                })
            return rows
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"Global news fetch failed: {e}")
        return []


async def _fetch_macro_data() -> Optional[dict]:
    """Fetch latest macro economic data: PMI, CPI, social financing."""
    try:
        import akshare as ak

        def _get():
            result = {}
            # CPI
            try:
                cpi_df = ak.macro_china_cpi_monthly()
                if cpi_df is not None and not cpi_df.empty:
                    # Data is oldest-first; find the latest row with a valid value
                    val_col = "值" if "值" in cpi_df.columns else cpi_df.columns[2]
                    date_col = "日期" if "日期" in cpi_df.columns else cpi_df.columns[1]
                    valid = cpi_df[cpi_df[val_col].notna()]
                    if not valid.empty:
                        latest = valid.iloc[-1]
                        result["cpi"] = {
                            "date": str(latest[date_col]),
                            "national_yoy": float(latest[val_col]),
                        }
            except Exception:
                pass

            # PMI
            try:
                pmi_df = ak.macro_china_pmi()
                if pmi_df is not None and not pmi_df.empty:
                    # Data is newest-first; take first row
                    latest = pmi_df.iloc[0]
                    result["pmi"] = {
                        "date": str(latest.get("月份", latest.iloc[0] if len(latest) > 0 else "")),
                        "manufacturing": float(latest.get("制造业-指数", 0) or 0),
                        "non_manufacturing": float(latest.get("非制造业-指数", 0) or 0),
                    }
            except Exception:
                pass

            # Social financing
            try:
                sf_df = ak.macro_china_social_financing()
                if sf_df is not None and not sf_df.empty:
                    latest = sf_df.iloc[-1]
                    result["social_financing"] = {
                        "date": str(latest.iloc[0]) if len(latest) > 0 else "",
                        "value_yi": round(float(latest.iloc[1]) / 1e8, 2) if len(latest) > 1 and latest.iloc[1] else 0,
                    }
            except Exception:
                pass

            return result if result else None
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning(f"Macro data fetch failed: {e}")
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
    """Call LLM to synthesize trading advice using sentiment framework + trading rules."""

    # ── Build data summaries ──

    # Overseas market
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
    market_summary = "\n".join(market_lines) if market_lines else "暂无"

    # FX
    fx_summary = ""
    if market_data.get("fx"):
        fx_summary = "人民币: "
        for f in market_data["fx"]:
            fx_summary += f"{f['name']}: {f['close']} ({f['change_pct']:+.2f}%) "

    # Chinese ADRs
    adr_up = 0
    adr_total = 0
    adr_lines = []
    for a in market_data.get("chinese_adrs", [])[:13]:
        adr_lines.append(f"  {a['name']}({a['symbol']}): {a['close']} ({a['change_pct']:+.2f}%)")
        if a.get("change_pct", 0) > 0:
            adr_up += 1
        adr_total += 1
    adr_ratio = round(adr_up / adr_total * 100) if adr_total > 0 else 50
    adr_summary = "\n".join(adr_lines) if adr_lines else "暂无中概股数据"

    # Market sentiment
    sent = market_data.get("market_sentiment") or {}
    sent_lines = []
    limit_up = sent.get("limit_up_count", 0)
    limit_down = sent.get("limit_down_count", 0)
    bust_rate = sent.get("bust_rate_pct", 0)
    max_streak = sent.get("max_streak", 0)
    vol_chg = sent.get("volume_change_pct")
    if limit_up:
        sent_lines.append(f"涨停{limit_up}家 跌停{limit_down}家 炸板率{bust_rate}%")
    if max_streak:
        sent_lines.append(f"最高连板: {max_streak}连板")
        for s in sent.get("top_streak_stocks", [])[:5]:
            detail = f"{s['name']}({s['code']}) {s['streak']}连板"
            if s.get("seal_amount_wan"):
                detail += f" 封单{s['seal_amount_wan']}万"
            if s.get("first_seal_time"):
                detail += f" 首封{s['first_seal_time']}"
            if s.get("bust_count"):
                detail += f" 炸板{s['bust_count']}次"
            detail += f" 行业:{s.get('reason', '')}"
            sent_lines.append(f"  {detail}")
    if vol_chg is not None:
        direction = "放量" if vol_chg > 0 else "缩量"
        sent_lines.append(f"量能: {direction}{abs(vol_chg):.1f}%")
    sentiment_summary = "\n".join(sent_lines) if sent_lines else "暂无"

    # North-bound
    nb = market_data.get("north_bound") or {}
    nb_summary = f"沪股通{nb.get('hgt_net', 'N/A')}亿 深股通{nb.get('sgt_net', 'N/A')}亿 合计{nb.get('total_net', 'N/A')}亿" if nb else "暂无（2024年后已停止逐日披露）"

    # Dragon tiger
    dt = market_data.get("dragon_tiger") or {}
    dt_lines = []
    if dt.get("institution_net") is not None:
        dt_lines.append(f"机构净买入: {dt['institution_net']}亿")
    for s in dt.get("top_net_buy", [])[:5]:
        dt_lines.append(f"  {s['name']}({s['code']}) 净买{s['net_buy_wan']}万 买{s.get('buy_wan', '?')}万 卖{s.get('sell_wan', '?')}万")
    dt_summary = "\n".join(dt_lines) if dt_lines else "暂无龙虎榜数据"

    # Industry ranking
    ind = market_data.get("industry_ranking") or {}
    ind_lines = []
    for r in ind.get("top", [])[:5]:
        ind_lines.append(f"  ↑{r['name']}: {r['change_pct']:+.2f}% 涨{r.get('up_count', 0)}跌{r.get('down_count', 0)} 领涨:{r.get('leader', '')}")
    for r in ind.get("bottom", [])[:3]:
        ind_lines.append(f"  ↓{r['name']}: {r['change_pct']:+.2f}%")
    industry_summary = "\n".join(ind_lines) if ind_lines else "暂无行业数据"

    # Sector fund flow
    sff = market_data.get("sector_fund_flow") or {}
    sff_lines = []
    for r in sff.get("top_inflow", [])[:5]:
        sff_lines.append(f"  →流入: {r['name']} 净流入{r['net_inflow_yi']}亿")
    for r in sff.get("top_outflow", [])[:3]:
        sff_lines.append(f"  ←流出: {r['name']} 净流出{r['net_inflow_yi']}亿")
    sff_summary = "\n".join(sff_lines) if sff_lines else "暂无板块资金流向数据"

    # Hot stocks
    hot_lines = []
    for h in market_data.get("hot_stocks", [])[:15]:
        hot_lines.append(f"  {h['name']}({h['code']}) {h['change_pct']:+.2f}% 换手{h.get('turnover', 'N/A')}% 题材: {h.get('reason', '')}")
    hot_summary = "\n".join(hot_lines) if hot_lines else "暂无"

    # Global news
    gn_lines = []
    for n in market_data.get("global_news", [])[:15]:
        gn_lines.append(f"- {n['title']}")
    global_news_summary = "\n".join(gn_lines) if gn_lines else "暂无"

    # Macro
    macro = market_data.get("macro_data") or {}
    macro_lines = []
    if macro.get("pmi"):
        macro_lines.append(f"PMI({macro['pmi'].get('date', '')}): 制造业{macro['pmi'].get('manufacturing', 'N/A')} 非制造业{macro['pmi'].get('non_manufacturing', 'N/A')}")
    if macro.get("cpi"):
        macro_lines.append(f"CPI({macro['cpi'].get('date', '')}): 同比{macro['cpi'].get('national_yoy', 'N/A')}%")
    macro_summary = "\n".join(macro_lines) if macro_lines else "暂无"

    # Top news
    news_lines = []
    for n in top_news[:10]:
        news_lines.append(f"- {n['title']}")
    news_summary = "\n".join(news_lines) if news_lines else "暂无"

    # Announcements
    announce = market_data.get("announcements") or {}
    announce_lines = []
    for ev in announce.get("major_events", [])[:10]:
        announce_lines.append(f"  [重大] {ev['name']}({ev['code']}): {ev['title']}")
    for ev in announce.get("shareholder_changes", [])[:5]:
        announce_lines.append(f"  [持股] {ev['name']}({ev['code']}): {ev['title']}")
    announce_summary = "\n".join(announce_lines) if announce_lines else "暂无个股公告"

    # Watchlist
    wl_lines = []
    for w in watchlist_analysis:
        price = w.get('latest_price', 'N/A')
        chg = w.get('change_pct', 'N/A')
        dl = w.get("decision_line")
        bl = w.get("bull_line")
        ol = w.get("orbit_line")
        od = w.get("orbit_direction", 0)
        levels = []
        if bl: levels.append(f"牛线{bl:.2f}")
        if dl: levels.append(f"决策线{dl:.2f}")
        if ol: levels.append(f"轨道{ol:.2f}({'多' if od > 0 else '空'})")
        signals_str = ", ".join(s["name"] for s in w.get("signals", [])) or "无"
        news_str = w.get('news_summary', '')[:60].replace("\n", " ")
        wl_lines.append(
            f"  {w['symbol']} {w['name']}: 现价{price} 涨跌{chg}% "
            f"| {'; '.join(levels) if levels else '无关键位'} "
            f"| 信号:{signals_str}"
            f"{' | 消息:' + news_str if news_str else ''}"
        )
    watchlist_summary = "\n".join(wl_lines) if wl_lines else "暂无自选股"

    # Portfolio
    pf_lines = []
    for p in portfolio_analysis:
        dl = p.get("decision_line")
        ol = p.get("orbit_line")
        od = p.get("orbit_direction", 0)
        levels = []
        if dl: levels.append(f"决策线{dl:.2f}")
        if ol: levels.append(f"轨道{ol:.2f}({'多' if od > 0 else '空'})")
        pf_lines.append(
            f"  {p['symbol']} {p['name']}: 成本{p['avg_cost']} 现价{p.get('current_price', 'N/A')} "
            f"盈亏{p.get('pnl_pct', 'N/A')}% "
            f"| {'; '.join(levels) if levels else '无关键位'} "
            f"| 风险:{', '.join(p.get('risk_signals', [])) or '无'}"
        )
    portfolio_summary = "\n".join(pf_lines) if pf_lines else "暂无持仓"

    today_str = datetime.now(timezone.utc).strftime("%m月%d日")

    # ── Build prompt ──
    prompt = f"""# Role
你是一位精通中国A股的顶级短线职业交易员。你的交易风格是【短线低吸与趋势潜伏】，核心原则是【绝不打板、绝不追高（涨幅>5%）、利用恐慌低吸、利用分歧布局】。

# Task
根据今日盘前原始数据，进行深度清洗、逻辑推演，输出极简、可扫读的盘前决策指令。

# 盘前原始数据

## 海外市场
{market_summary}
{fx_summary}

## 中概股龙头隔夜表现（上涨{adr_ratio}%）
{adr_summary}

## A股昨日情绪
{sentiment_summary}

## 北向资金
{nb_summary}

## 龙虎榜与机构动向
{dt_summary}

## 行业板块涨跌排名
{industry_summary}

## 板块资金流向（主力净买/净卖）
{sff_summary}

## 今日强势股与题材归因
{hot_summary}

## 全球财经快讯
{global_news_summary}

## 宏观经济数据
{macro_summary}

## 重大公告与减持预警
{announce_summary}

## 重大宏观要闻
{news_summary}

## 自选股技术面与消息
{watchlist_summary}

## 持仓股盈亏与风险
{portfolio_summary}

# 判断逻辑（你必须严格按照此逻辑推演）

## 1. 情绪晴雨表（综合外盘+昨日内部温度）
外盘信号：
- A50期货 >+1% 且 ADR >70%上涨 → 强多，大概率高开
- A50期货 <-1% 且 ADR <30%上涨 → 强空，大概率低开
- A50期货 ±0.5% 或 ADR涨跌互现 → 中性，平开

昨日内部温度：
- 涨停>80家 且 跌停<5家 且 炸板率<25% → 高潮（过热，次日分歧风险大）
- 涨停50-80家 且 炸板率25-40% → 升温（正常赚钱效应）
- 涨停30-50家 → 平衡（结构性行情）
- 涨停<30家 且 跌停>20家 且 炸板率>40% → 冰点（恐慌，次日反弹概率大）

量能信号：
- 放量>20% + 阳线 → 强势，新资金进场
- 放量>20% + 阴线 → 恐慌出逃
- 缩量>10% → 观望，变盘前兆

## 2. 组合决策矩阵（外盘 × 内部温度 × 量能 → 仓位+策略）

| 外盘 | 内部 | 量能 | 情绪 | 仓位 | 策略 |
|------|------|------|------|------|------|
| A50↑+ADR↑ | 高潮 | 缩量 | 情绪高潮 | 0-3成 | 不追高！找补涨品种或等分歧 |
| A50↑+ADR↑ | 升温/平衡 | 放量阳 | 内外共振 | 5-7成 | 积极做多，主攻主线 |
| A50↑+ADR↑ | 冰点 | 放量阴 | 外热内冷 | 1-3成 | 警惕高开低走，多看少动 |
| A50↓+ADR↓ | 高潮 | 放量阳 | 外冷内热 | 3-5成 | 低开高走概率大，低吸主线 |
| A50↓+ADR↓ | 升温/平衡 | 缩量 | 偏弱 | 1-3成 | 轻仓等方向 |
| A50↓+ADR↓ | 冰点 | 放量阴 | 恐慌冰点 | 0-2成 | 等恐慌释放，尾盘再定 |
| 信号矛盾 | 任意 | 任意 | 混沌 | 1-3成 | 多看少动，专注个股 |

## 3. 公告过滤规则
- 个股处于高位（近20日涨>30%或近60日新高）+ 发布利好公告 → 主力借利好出货，不关注
- 个股处于低位（近20日跌>15%或近60日新低）+ 发布利好公告 → 底部催化剂，重点观察
- 个股出现减持公告 → 一律回避，无论位置

## 4. 龙虎榜解读规则
- 机构/游资净买入 + 当日K线收阴（或炸板）→ "分歧股"，次日弱转强概率大，列为低吸候选
- 机构/游资净买入 + 当日涨停封板 → 一致看多，无舒服买点，不追
- 机构净卖出 + 高位股 → 主力撤退，回避

## 5. 板块资金流向规则
- 主力净流入TOP3板块 + 板块涨幅在涨幅榜TOP10 → 有量有价，可确认为主线
- 板块涨幅TOP3但主力净流出 → 虚涨，不可追
- 板块主力净流入但板块下跌 → 主力借跌吸筹，关注板块内龙头

# 输出格式（严格按以下Markdown格式输出，禁止任何寒暄和多余解释）

## 🧭 今日情绪与仓位策略
- **情绪判断**：[高潮/升温/平衡/冰点/恐慌冰点]
- **大盘预期**：[看多/看空/震荡] 理由：[一句话说明外盘与内部温度的综合判断]
- **今日仓位**：[0-3成 / 3-5成 / 5-7成]
- **核心战法**：[如：等恐慌低吸 / 主线首阴博弈 / 底部利好潜伏 / 多看少动]

## 📊 今日主线方向
- **主线一**：[板块名称] — 理由：[资金+涨幅+消息共振逻辑，不超过15字]
- **主线二**：[板块名称] — 理由：[同上]
- **回避板块**：[板块名称] — 理由：[高位+利好出尽/主力流出/减持等]

## 🎯 自选股进攻计划
（必须覆盖全部自选股，每只都要写）

* **[代码.名称]** [战法：首阴低吸/趋势回踩/底部潜伏/消息驱动/观望]
  - **逻辑**：[不超过15字的理由]
  - **买入触发**：[如：竞价平开/微高开<2%，开盘后分时回踩轨道线XX元附近缩量企稳，买入1层仓]
  - **放弃条件**：[如：直接高开>3%放弃 / 低开破XX元放弃 / 9:45前不放量放弃]
  - **止损位**：[具体价位或条件]

## 🛡️ 持仓防守计划
（必须覆盖全部持仓股，每只都要写）

* **[代码.名称]** 盈亏{{盈亏}}%
  - **主线匹配**：[当前是否在今日风口，是否汰弱留强]
  - **止盈条件**：[如：冲高不封板在+3%~+5%分批止盈]
  - **止损条件**：[如：跌破XX元无条件清仓]
  - **动作**：[持有/减仓/加仓/清仓]

## ⚠️ 风险提示
- [今日最大风险，如：高开低走/恐慌蔓延/利好落地变利空/无量反弹]
- [需要回避的个股或板块黑名单]"""

    # ── Call LLM ──
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

    provider_map = {"deepseek": "openai", "zhipu": "openai", "moonshot": "openai"}
    mapped_provider = provider_map.get(provider.lower(), provider.lower())

    try:
        from tradingagents.llm_clients.factory import create_llm_client

        client = create_llm_client(provider=mapped_provider, model=model, base_url=base_url, api_key=api_key)
        llm = client.get_llm()
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        content = content.strip()
        # Remove outer code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[-1].strip() == "```":
                content = "\n".join(lines[1:-1])
            else:
                content = "\n".join(lines[1:])

        # Parse key sections from markdown for structured access
        sentiment_line = ""
        for line in content.split("\n"):
            line_s = line.strip()
            if line_s.startswith("- **情绪判断**") or line_s.startswith("- **大盘预期**") or "情绪判断" in line_s:
                sentiment_line = line_s.lstrip("- *").strip()
                break

        return {
            "content": content,
            "sentiment": sentiment_line or content.split("\n")[0] if content else "",
            "watchlist_plan": [],
            "portfolio_plan": [],
        }
    except Exception as e:
        logger.error(f"LLM trading advice generation failed: {e}")
        return {
            "content": "",
            "sentiment": "AI建议生成失败，请参考其他板块数据手动判断",
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
        # Phase 1: Fetch ALL market data sources in parallel
        mkt_task = _fetch_overseas_market()
        fund_task = _fetch_fund_flow_summary()
        news_task = _fetch_top_news(date_str)
        a50_task = _fetch_a50_futures_v2()
        adr_task = _fetch_chinese_adrs()
        senti_task = _fetch_market_sentiment(date_str)
        nb_task = _fetch_north_bound()
        dt_task = _fetch_dragon_tiger(date_str)
        industry_task = _fetch_industry_ranking()
        hot_task = _fetch_hot_stocks()
        gnews_task = _fetch_global_news_fast()
        macro_task = _fetch_macro_data()
        sector_fund_task = _fetch_sector_fund_flow()
        announce_task = _fetch_stock_announcements(date_str)

        (market_data, fund_flow, top_news, a50, adrs, sentiment,
         north_bound, dragon_tiger, industry, hot_stocks, global_news, macro_data,
         sector_fund_flow, announcements,
        ) = await asyncio.gather(
            mkt_task, fund_task, news_task, a50_task, adr_task, senti_task,
            nb_task, dt_task, industry_task, hot_task, gnews_task, macro_task,
            sector_fund_task, announce_task,
            return_exceptions=True,
        )

        if isinstance(market_data, Exception):
            market_data = {"error": str(market_data)}
        if isinstance(fund_flow, Exception):
            fund_flow = None
        if isinstance(top_news, Exception):
            top_news = []
        if isinstance(a50, Exception):
            a50 = None
        if isinstance(adrs, Exception):
            adrs = []
        if isinstance(sentiment, Exception):
            sentiment = None
        if isinstance(north_bound, Exception):
            north_bound = None
        if isinstance(dragon_tiger, Exception):
            dragon_tiger = None
        if isinstance(industry, Exception):
            industry = None
        if isinstance(hot_stocks, Exception):
            hot_stocks = []
        if isinstance(global_news, Exception):
            global_news = []
        if isinstance(macro_data, Exception):
            macro_data = None
        if isinstance(sector_fund_flow, Exception):
            sector_fund_flow = None
        if isinstance(announcements, Exception):
            announcements = None

        # Enrich market_data with all new sections
        market_data["fund_flow"] = fund_flow
        if a50:
            market_data["a50_futures"] = a50
        market_data["chinese_adrs"] = adrs
        market_data["market_sentiment"] = sentiment
        market_data["north_bound"] = north_bound
        market_data["dragon_tiger"] = dragon_tiger
        market_data["industry_ranking"] = industry
        market_data["hot_stocks"] = hot_stocks
        market_data["global_news"] = global_news
        market_data["macro_data"] = macro_data
        market_data["sector_fund_flow"] = sector_fund_flow
        market_data["announcements"] = announcements

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
