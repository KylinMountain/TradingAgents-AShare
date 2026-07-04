"""同花顺概念板块共振分析模块

按需触发 + 3交易日缓存TTL：仅在用户对某只股票发起分析时计算，不扫全量。
仅使用同花顺"概念"类型板块，行业板块不参与共振计算。

流程：
1. 复用 watchlist_service.fetch_stock_concepts() 取同花顺概念列表
2. 检查缓存，3个交易日内命中直接返回
3. 未命中 → 名称→代码映射 → 拉取K线 → Pearson相关 → 共振评分
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── 缓存配置 ──
CACHE_TTL_DAYS = 3  # 缓存有效期（交易日数）
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "resonance_cache")
FLAT_VOLATILITY_THRESHOLD = 0.005  # 日收益率标准差 < 0.5% 视为横盘
MIN_VALID_DAYS = 36  # 60日窗口中最少有效交易日数
MAX_CONSECUTIVE_ZERO = 3  # 连续零涨幅日超过此值视为疑似停牌
PEARSON_WINDOW = 60  # 相关系数计算窗口（约3个月）

# 模块级缓存：名称→代码映射表（模块加载时构建一次）
_name_to_code: Optional[Dict[str, str]] = None
_name_to_code_lock = threading.Lock()


def _bypass_proxy():
    """临时绕过代理，返回还原函数。akshare 直连东方财富等需要绕过代理。"""
    old = {
        "no_proxy": os.environ.get("NO_PROXY", ""),
        "http_proxy": os.environ.get("HTTP_PROXY", ""),
        "https_proxy": os.environ.get("HTTPS_PROXY", ""),
    }
    os.environ["NO_PROXY"] = "*"
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)
    return old


def _restore_proxy(old: Dict[str, str]):
    """还原代理设置。"""
    for k, v in old.items():
        if v:
            os.environ[k.upper()] = v
        else:
            os.environ.pop(k.upper(), None)


@dataclass
class BoardInfo:
    """单个概念板块的共振信息"""
    name: str
    correlation: float  # Pearson 相关系数
    direction: str  # "涨" / "跌" / "平"
    strength: float  # 近5日平均涨跌幅%绝对值


@dataclass
class ConceptResonanceResult:
    """概念共振分析结果"""
    resonance_score: float  # -1 到 +1，正=跟涨，负=跟跌，0=无共振
    leading_boards: List[BoardInfo] = field(default_factory=list)
    board_trend_summary: str = ""
    divergence_alert: bool = False  # 所有概念均不相关
    board_disagreement: bool = False  # 主导板块间方向不一致
    is_flat: bool = False  # 个股横盘，无法计算
    insufficient_data: bool = False  # 有效交易日不足
    warnings: List[str] = field(default_factory=list)
    computed_at: str = ""  # 计算日期


def _build_name_to_code_map() -> Dict[str, str]:
    """构建同花顺概念板块名称→代码映射表。模块加载时执行一次，线程安全。"""
    global _name_to_code
    with _name_to_code_lock:
        if _name_to_code is not None:
            return _name_to_code

        try:
            import akshare as ak
            boards = ak.stock_board_concept_name_ths()
            _name_to_code = dict(zip(boards["name"].str.strip(), boards["code"].astype(str)))
            logger.info("同花顺概念板块映射表构建完成：%d 个概念", len(_name_to_code))
        except Exception as e:
            logger.error("构建概念板块映射表失败：%s", e)
            _name_to_code = {}
        return _name_to_code


def _load_cache(symbol: str, trade_date: str) -> Optional[ConceptResonanceResult]:
    """从磁盘缓存加载共振结果。"""
    cache_file = os.path.join(CACHE_DIR, f"{symbol}.json")
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, encoding="utf-8") as f:
            data = json.load(f)
        cached_date = data.get("computed_at", "")
        if not cached_date:
            return None

        # 检查缓存是否在3个交易日内
        cached_dt = datetime.strptime(cached_date, "%Y-%m-%d")
        target_dt = datetime.strptime(trade_date, "%Y-%m-%d")
        if abs((target_dt - cached_dt).days) <= CACHE_TTL_DAYS:
            result = ConceptResonanceResult(
                resonance_score=data.get("resonance_score", 0.0),
                leading_boards=[
                    BoardInfo(**b) for b in data.get("leading_boards", [])
                ],
                board_trend_summary=data.get("board_trend_summary", ""),
                divergence_alert=data.get("divergence_alert", False),
                board_disagreement=data.get("board_disagreement", False),
                is_flat=data.get("is_flat", False),
                insufficient_data=data.get("insufficient_data", False),
                warnings=data.get("warnings", []),
                computed_at=cached_date,
            )
            return result
    except Exception as e:
        logger.warning("读取概念共振缓存失败 %s: %s", symbol, e)
    return None


def _save_cache(symbol: str, result: ConceptResonanceResult) -> None:
    """将共振结果写入磁盘缓存。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{symbol}.json")
    try:
        data = {
            "resonance_score": result.resonance_score,
            "leading_boards": [
                {"name": b.name, "correlation": b.correlation,
                 "direction": b.direction, "strength": b.strength}
                for b in result.leading_boards
            ],
            "board_trend_summary": result.board_trend_summary,
            "divergence_alert": result.divergence_alert,
            "board_disagreement": result.board_disagreement,
            "is_flat": result.is_flat,
            "insufficient_data": result.insufficient_data,
            "warnings": result.warnings,
            "computed_at": result.computed_at,
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("保存概念共振缓存失败 %s: %s", symbol, e)


def _fetch_stock_daily_returns(symbol: str, trade_date: str) -> Tuple[Optional[pd.Series], List[str]]:
    """获取个股近60日（约3个月）收益率序列。返回 (收益率Series, 警告列表)。"""
    warnings = []
    try:
        import akshare as ak

        start_date = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=120)).strftime("%Y%m%d")
        end_date = trade_date.replace("-", "")

        code = symbol.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")

        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if df is None or df.empty:
            return None, ["个股K线数据为空"]

        # 标准化列名：akshare返回中文列名
        close_col = "收盘" if "收盘" in df.columns else "close"
        date_col = "日期" if "日期" in df.columns else "date"

        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col).tail(PEARSON_WINDOW + 5)
        df["pct"] = df[close_col].pct_change()

        df = df.dropna(subset=["pct"])
        df = df[df["pct"].abs() <= 0.15]

        if len(df) < MIN_VALID_DAYS:
            return None, [f"有效交易日不足：{len(df)}天 < {MIN_VALID_DAYS}天"]

        # 检查连续零涨幅
        zero_run = (df["pct"].abs() < 0.0001).astype(int)
        consecutive = zero_run.groupby((zero_run != zero_run.shift()).cumsum()).transform("sum")
        if (consecutive >= MAX_CONSECUTIVE_ZERO).any():
            warnings.append("疑似停牌：连续3日以上零涨幅")

        returns = df["pct"].tail(PEARSON_WINDOW).reset_index(drop=True)
        return returns, warnings

    except Exception as e:
        return None, [f"获取个股数据异常: {e}"]


def _fetch_board_returns(board_name: str, end_date: str) -> Optional[pd.Series]:
    """获取概念板块指数近60日（约3个月）收益率序列。

    Args:
        board_name: 同花顺概念板块名称（中文），如'PCB概念'。
                    注意：stock_board_concept_index_ths 只接受中文名，不接受数字代码。
    """
    try:
        import akshare as ak
        start_date = (datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=120)).strftime("%Y-%m-%d")
        df = ak.stock_board_concept_index_ths(symbol=board_name, start_date=start_date, end_date=end_date)

        if df is None or df.empty:
            return None

        # 列名标准化：同花顺返回中文列名
        col_map = {}
        for c in df.columns:
            if c in ("日期", "date"):
                col_map[c] = "date"
            elif c in ("收盘价", "close"):
                col_map[c] = "close"
        df = df.rename(columns=col_map)

        if "close" not in df.columns:
            return None

        df = df.sort_values("date")
        df["pct"] = df["close"].pct_change()
        df = df.dropna(subset=["pct"])
        df = df[df["pct"].abs() <= 0.15]

        if len(df) < MIN_VALID_DAYS // 2:
            return None

        return df["pct"].tail(PEARSON_WINDOW)

    except Exception as e:
        logger.debug("获取板块 %s K线失败: %s", board_name, e)
        return None


def _pearson_corr(a: pd.Series, b: pd.Series) -> float:
    """计算两个序列的 Pearson 相关系数（按最短长度对齐）。"""
    min_len = min(len(a), len(b))
    if min_len < MIN_VALID_DAYS:
        return 0.0
    a_vals = a.tail(min_len).values.astype(float)
    b_vals = b.tail(min_len).values.astype(float)
    corr = np.corrcoef(a_vals, b_vals)[0, 1]
    return 0.0 if np.isnan(corr) else float(corr)


def extract_returns_from_df(df: pd.DataFrame, window: int = PEARSON_WINDOW) -> Optional[pd.Series]:
    """从已解析的OHLCV DataFrame提取日收益率序列。复用DataCollector已有的K线数据。"""
    if df is None or df.empty or "close" not in df.columns:
        return None
    df = df.copy()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
    df["pct"] = df["close"].pct_change()
    df = df.dropna(subset=["pct"])
    df = df[df["pct"].abs() <= 0.15]
    if len(df) < MIN_VALID_DAYS:
        return None
    return df["pct"].tail(window).reset_index(drop=True)


def compute_concept_resonance(
    symbol: str,
    trade_date: str,
    stock_returns: Optional[pd.Series] = None,
) -> ConceptResonanceResult:
    """计算个股与同花顺概念板块的共振关系。

    Args:
        symbol: 股票代码，如 '300476.SZ' 或 '300476'
        trade_date: 分析日期，格式 YYYY-MM-DD
        stock_returns: 预计算的个股日收益率序列（由DataCollector传入，复用供应商链路）。
                       为None时自动通过akshare拉取（独立调用场景）。

    Returns:
        ConceptResonanceResult
    """
    # ── 1. 检查缓存 ──
    cached = _load_cache(symbol, trade_date)
    if cached is not None:
        return cached

    # ── 2. 归一化 symbol 格式 ──
    normalized = symbol.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")

    # ── 3. 获取概念板块列表 ──
    try:
        from api.services.watchlist_service import fetch_stock_concepts
        all_boards = fetch_stock_concepts(normalized)
    except Exception as e:
        logger.warning("获取概念板块列表失败 %s: %s", symbol, e)
        return ConceptResonanceResult(
            resonance_score=0.0,
            insufficient_data=True,
            warnings=[f"获取概念列表失败: {e}"],
            computed_at=trade_date,
        )

    concept_boards = [b for b in all_boards if b.get("type") == "概念"]
    if not concept_boards:
        return ConceptResonanceResult(
            resonance_score=0.0,
            divergence_alert=True,
            warnings=["无同花顺概念板块数据"],
            computed_at=trade_date,
        )

    # ── 4. 获取个股收益率（优先使用DataCollector传入的序列，复用供应商链路）──
    warnings: List[str] = []
    if stock_returns is not None and len(stock_returns) >= MIN_VALID_DAYS:
        # 截取窗口
        stock_returns = stock_returns.tail(PEARSON_WINDOW).reset_index(drop=True)
    else:
        stock_returns, warnings = _fetch_stock_daily_returns(symbol, trade_date)

    if stock_returns is None:
        return ConceptResonanceResult(
            resonance_score=0.0,
            insufficient_data=True,
            warnings=warnings,
            computed_at=trade_date,
        )

    # 波动率前置检查
    stock_vol = float(stock_returns.std())
    if stock_vol < FLAT_VOLATILITY_THRESHOLD:
        return ConceptResonanceResult(
            resonance_score=0.0,
            is_flat=True,
            warnings=[f"个股20日波动率过低({stock_vol:.4f})，近横盘状态"] + warnings,
            computed_at=trade_date,
        )

    # ── 5. 验证概念在THS系统中存在 ──
    name_to_code = _build_name_to_code_map()

    # ── 6. 计算每个概念板块的相关系数 ──
    board_results: List[Dict[str, Any]] = []
    for board in concept_boards:
        board_name = board["name"].strip()

        # 验证概念在THS系统中存在
        if board_name not in name_to_code:
            warnings.append(f"概念'{board_name}'未出现在THS概念板块列表中，跳过")
            continue

        board_returns = _fetch_board_returns(board_name, trade_date)
        if board_returns is None:
            continue

        corr = _pearson_corr(stock_returns, board_returns)
        direction = "涨" if board_returns.mean() > 0 else "跌"
        strength = abs(float(board_returns.tail(5).mean())) * 100

        if abs(corr) < 0.1:
            continue

        board_results.append({
            "name": board_name,
            "correlation": corr,
            "direction": direction,
            "strength": strength,
        })

    # ── 7. 排序取主导板块 ──
    board_results.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    leading = board_results[:5]

    # ── 8. 方向分歧检测 ──
    up_count = sum(1 for b in leading if b["direction"] == "涨")
    down_count = len(leading) - up_count

    board_disagreement = False
    if len(leading) >= 2 and up_count > 0 and down_count > 0:
        board_disagreement = True
        resonance_score = (up_count - down_count) / max(len(leading), 1) * 0.3
    elif len(leading) > 0:
        # 方向一致
        direction_sign = 1 if up_count > down_count else -1
        avg_corr = sum(abs(b["correlation"]) for b in leading) / len(leading)
        avg_strength = sum(b["strength"] for b in leading) / len(leading)
        resonance_score = direction_sign * avg_corr * min(avg_strength / 5.0, 1.0)
        resonance_score = max(-1.0, min(1.0, resonance_score))
    else:
        resonance_score = 0.0

    # ── 9. 构建摘要 ──
    divergence_alert = len(leading) == 0
    leading_boards = [
        BoardInfo(**b) for b in leading
    ]

    if leading:
        names = "、".join(b["name"] for b in leading[:3])
        up_label = "跟涨" if resonance_score > 0 else "跟跌"
        direction_label = "（方向分裂）" if board_disagreement else f"（{up_label}）"
        board_trend_summary = f"主导概念：{names}。共振评分：{resonance_score:.2f}{direction_label}"
    else:
        board_trend_summary = "无主导概念板块，个股与各概念板块均无显著相关"

    result = ConceptResonanceResult(
        resonance_score=round(resonance_score, 2),
        leading_boards=leading_boards,
        board_trend_summary=board_trend_summary,
        divergence_alert=divergence_alert,
        board_disagreement=board_disagreement,
        is_flat=False,
        insufficient_data=False,
        warnings=warnings,
        computed_at=trade_date,
    )

    # ── 10. 写缓存 ──
    _save_cache(symbol, result)

    return result


def format_resonance_for_prompt(result: ConceptResonanceResult) -> str:
    """将共振结果格式化为注入提示词的中文文本。"""
    if result.insufficient_data:
        return "【概念共振】数据不足，无法计算概念板块共振关系。"

    if result.is_flat:
        return "【概念共振】个股近20日处于横盘状态（波动率过低），无法通过板块共振验证。建议等待方向突破后再决策。"

    if result.divergence_alert:
        return "【概念共振】[!] 个股与所属各概念板块均无显著相关性（相关系数<0.1），走独立行情。缺乏板块共振支撑，信号置信度应降低。"

    lines = ["【概念共振】"]
    lines.append(f"共振评分：{result.resonance_score:+.2f}（范围-1到+1，正=跟涨，负=跟跌）")

    if result.board_disagreement:
        lines.append("[!] 主导板块方向分裂：")

    for b in result.leading_boards:
        lines.append(
            f"  {b.name}：相关系数 {b.correlation:+.2f}，{b.direction}，"
            f"近5日强度 {b.strength:.1f}%"
        )

    lines.append(f"摘要：{result.board_trend_summary}")

    if result.warnings:
        lines.append(f"数据提示：{'；'.join(result.warnings)}")

    return "\n".join(lines)
