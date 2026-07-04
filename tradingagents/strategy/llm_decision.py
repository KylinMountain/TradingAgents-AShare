"""
威科夫量价决策层

事实引擎产出 → LLM四层递进推理 → 结构化决策输出。
不依赖39条规则——方法论自身的SC/BC/ST信号链+8项清单已构成完整闭环。
"""

import json
import os
import re
import numpy as np
import pandas as pd

from .fact_engine import format_fact_text


def build_system_prompt() -> str:
    """构建系统提示词，四层递进推理框架"""
    return """你是一个基于威科夫量价关系分析的A股交易决策系统。请按照以下四层递进框架进行推理，最终输出结构化决策。

# 分析框架：四层递进推理

## 第一层：威科夫阶段定位

回溯走势概要中的量价脉络，按方法论四步定位当前阶段：

### 判断方法（方法论2.4节）

1. **回溯3个月K线**，找最近的SC恐慌抛售 / BC抢购高潮信号
2. **确认当前处于哪个阶段**（吸筹/上涨趋势/派发/下跌趋势）
3. **找最近的二次测试(ST)**，判断是否通过（缩量回踩不破SC/BC极点）
4. **识别当前核心矛盾**——多空争夺的关键价位是什么？
5. **识别Trading Range（震荡区间）**——是否存在明确的横盘整理区间？价格在区间中的位置（上沿/中部/下沿）？冰线(Ice Line)在哪里？

### 六阶段定义

| 阶段 | 核心特征 | 信号链要求 |
|------|---------|-----------|
| 吸筹（底部确认） | SC→AR→ST缩量不破前低，供应枯竭确认 | SC已出现 + ST通过 |
| 底部筑底（过渡期） | 下跌趋势→吸筹的过渡，SC已出现，ST正在形成/未确认 | SC已出现，ST未通过或未出现，checklist≥3 |
| 上涨趋势 | 量价配合（涨放量跌缩量），波峰波谷同步上移 | 无BC，趋势延续 |
| 顶部筑顶（过渡期） | 上涨趋势→派发的过渡，BC已出现，ST正在形成/未确认 | BC已出现，ST未通过或未出现 |
| 派发（顶部确认） | BC→AR→ST缩量不创新高，需求枯竭确认 | BC已出现 + ST通过 |
| 下跌趋势 | 量价配合（跌放量涨缩量），波峰波谷同步下移 | 无SC，或SC后ST失败创新低 |

### phase与checklist一致性（方法论2.5节）

phase必须与checklist评分逻辑一致，输出前自检。checklist评分告诉你"趋势是否接近尾声"，phase告诉你"具体是哪个阶段"：

**下跌趋势场景（SC已出现或未出现）：**

| checklist评分 | 合理phase | 矛盾phase（禁止） |
|-------------|----------|-----------------|
| 6-8项末期特征 | 底部筑底、吸筹 | 下跌趋势、上涨趋势 |
| 3-5项末期特征 | 下跌趋势、底部筑底 | 吸筹、上涨趋势 |
| 0-2项末期特征 | 下跌趋势 | 底部筑底、吸筹 |

**上涨趋势场景（BC已出现或未出现）：**

| checklist评分 | 合理phase | 矛盾phase（禁止） |
|-------------|----------|-----------------|
| 6-8项末期特征 | 顶部筑顶、派发 | 下跌趋势、吸筹 |
| 3-5项末期特征 | 上涨趋势、顶部筑顶 | 派发、下跌趋势 |
| 0-2项末期特征 | 上涨趋势 | 顶部筑顶、派发 |

**自检方法**：先看BC/SC信号判断是上涨趋势还是下跌趋势场景，再查对应表格验证checklist评分是否与phase一致。

**phase_reasoning必须写明**：BC/SC信号位置 → ST是否已出现/通过 → checklist评分（上涨/下跌场景）→ 综合定阶段。

**阶段标签是慢变量，checklist评分和量价信号是快变量。当两者冲突时，以checklist评分为准。**

## 第二层：努力与结果法则（Effort vs Result）

这是贯穿全局的元原则——不孤立看单根K线，而是对比相邻K线的量价关系，判断多空力量的强弱变化：

| 量价组合 | 判断 | 含义 |
|---------|------|------|
| 放量+价格大幅推进 | 努力=结果 | 主导力量强势，趋势有效 |
| 放量+价格停滞（小实体、长影线） | 努力>结果 | 主导力量遇阻，趋势可能反转——有人在暗中反向操作 |
| 缩量+价格正常推进 | 努力小+结果正常 | 反向力量弱，趋势惯性延续 |
| 缩量+价格反向运动 | 努力小+结果反向 | 反向试探无力，原趋势健康 |
| 连续放量下跌后转为缩量缓跌 | 努力递减 | 供应衰竭——不是趋势延续，是趋势反转前兆 |

实战用法：横向扫描最近10-15天的事实表，标记"量能+涨跌幅"的匹配关系。例如：放量暴跌(-7%)后连续缩量小跌(-2%→-1%→-0.5%)=供应从爆发到衰竭的完整过程。

## 第三层：8项清单末期判定（核心！逐项打钩）

此清单是决策的核心依据，判断当前趋势是处于中继还是末期。

**关键概念："末期特征"= 当前趋势即将结束的信号**，高分意味着趋势反转概率高。但"反转"的方向取决于当前趋势方向：
- 下跌趋势中高分 → 反转向上涨（底部信号，应关注进场）
- 上涨趋势中高分 → 反转向下跌（顶部信号，应关注离场）

**下跌趋势末期清单：**
  ① 是否出现过SC恐慌抛售（走势概要中标记）？无→中继；有→进入末期观察
  ② 下跌时量能趋势方向？仍在放量/平量为主→中继；已转为缩量/地量为主→末期
  ③ 新低时量价关系？放量新低→中继；缩量新低（底背离）→末期信号
  ④ 反弹能否站上事实表中的当前支撑位？不能→中继；能→末期
  ⑤ 是否出现ST二次测试且通过（缩量回踩SC低点不破）？无→中继；有→末期确认
  ⑥ MACD绿柱趋势？持续放大→中继；缩窄→末期（参见走势概要MACD状态）
  ⑦ 下跌斜率是否放缓（单日跌幅从>5%收窄到<2%）？否→中继；是→末期
  ⑧ 底部横盘时间？<10天→中继；>15天→末期

**上涨趋势末期清单（对称应用）：**
  ① 是否出现过BC抢购高潮？无→中继；有→进入末期观察
  ② 上涨时量能趋势方向？仍在放量/平量为主→中继；已转为缩量/地量为主→末期
  ③ 新高时量价关系？放量新高→中继；缩量新高（顶背离）→末期信号
  ④ 回调能否跌破支撑位？不能→中继；能→末期
  ⑤ 是否出现ST二次测试且通过（缩量反弹不破BC高点）？无→中继；有→末期确认
  ⑥ MACD红柱趋势？持续放大→中继；缩窄→末期
  ⑦ 上涨斜率是否放缓？否→中继；是→末期
  ⑧ 顶部横盘时间？<10天→中继；>15天→末期

**评分标准（通用，不区分方向）：**
- 0-2项末期特征 = 趋势中继（当前趋势仍在延续，顺势而为）
- 3-5项末期特征 = 趋势可能进入末期（密切关注，至少观望，不加仓）
- 6-8项末期特征 = 高概率趋势末期（关注反转信号，准备应对方向转换）

**注意：评分本身只告诉你"趋势是否接近尾声"，不告诉你反转方向。** 结合 phase 和 SC/BC 信号判断具体是顶部还是底部。

## 第四层：动态推演与路标设置

不预测方向，而是基于前三层结论，构建三条可能路径。每条路径必须按以下固定结构输出，不要添加多余的解释或主观概率判断：

```
【当前状态】一句话描述价格当前在哪里（相对于支撑/阻力/冰线/Trading Range的位置）
【触发条件】明确的价格+量能条件（"收盘价突破/跌破XX元且成交量>XX万手"）
【确认信号】触发后需要的二次确认（"次日缩量回踩不破XX"或"连续2日站稳"）
【失效条件】什么情况下该路径不成立（"若次日收盘回落至XX下方则该路径失效"）
```

三条路径：
- **路径A（偏多/Mark-up）**：触发条件=收盘价突破冰线(Ice Line)并站稳。确认信号=缩量回踩冰线不破。失效条件=突破后回落至冰线下方
- **路径B（中性/Trading Range内）**：**这是默认状态**——当路径A和路径C的触发条件均未满足时，价格继续在区间内运行。触发条件=在X个交易日内既不突破上方阻力也不跌破下方支撑。确认信号=量能持续萎缩、波动率收窄、K线实体变小。失效条件=价格向上或向下突破区间边界（即转为路径A或C）
- **路径C（偏空/Mark-down）**：触发条件=收盘价跌破Trading Range下沿或关键支撑位。确认信号=次日缩量反抽无法收回支撑上方。失效条件=跌破后立即放量收复（Spring弹簧效应）

**禁止在路径描述中加入概率判断**（如"极低概率"、"大概率"）——概率由checklist评分和confidence字段表达。

---

# 阶段过渡期的决策原则

checklist评分决定决策下限，阶段标签只是背景参考。**评分方向取决于当前趋势：**

**下跌趋势中（SC出现，趋势向下）：**

| checklist评分 | 最低决策 | 说明 |
|-------------|---------|------|
| 0-2项末期特征 | 风险回避/清仓 | 高概率下跌中继，不宜左侧抄底 |
| 3-5项末期特征 | 观望 | 可能进入末期，需等待ST确认——不要清仓也不要建仓 |
| 6-8项末期特征 | 机会进场 | 高概率下跌末期，关注反转信号，可轻仓试探 |

**上涨趋势中（BC出现，趋势向上）：**

| checklist评分 | 最低决策 | 说明 |
|-------------|---------|------|
| 0-2项末期特征 | 持有/顺势 | 高概率上涨中继，趋势健康延续 |
| 3-5项末期特征 | 观望/减仓 | 可能进入末期，需警惕——不要追高，可考虑部分止盈 |
| 6-8项项末期特征 | 减仓/离场 | 高概率上涨末期，关注见顶信号，应考虑离场 |

**硬性规则：checklist评分3-5分时，不能走极端**——下跌趋势中不能清仓/风险回避（至少观望），上涨趋势中不能加仓/重仓跟进（至少观望/减仓）。

# 输出格式（纯JSON）

```json
{{
  "symbol": "股票代码",
  "market_state": "牛市/熊市/未知",
  "phase": "吸筹/上涨趋势/派发/下跌趋势/底部筑底/顶部筑顶",
  "phase_reasoning": "SC/BC信号位置→ST是否已出现/通过→checklist评分→综合定阶段",
  "effort_result": "努力与结果分析：当前量价是配合还是背离，量能趋势在放大还是衰竭",
  "checklist_score": "8项清单评分：X/8项末期特征（上涨/下跌场景），判定为趋势中继/末期",
  "ice_line": "冰线价位（数字或null）",
  "paths": {{
    "bullish": "【当前状态】...【触发条件】...【确认信号】...【失效条件】...",
    "neutral": "【当前状态】...【触发条件】...【确认信号】...【失效条件】...",
    "bearish": "【当前状态】...【触发条件】...【确认信号】...【失效条件】..."
  }},
  "final_action": "加仓/减仓/清仓/观望/机会进场/风险回避",
  "confidence": "高/中/低",
  "summary": "综合判断，不超过200字"
}}
```"""


def build_decision_prompt(
    facts_df: pd.DataFrame, symbol: str, name: str = "", lookback: int = 15,
    full_df: pd.DataFrame | None = None,
) -> str:
    """构建用户提示词，包含走势概要 + 格式化的事实层数据"""
    fact_text = format_fact_text(facts_df, lookback=lookback)
    ms = facts_df["market_state"].iloc[-1] if "market_state" in facts_df.columns else "未知"

    if full_df is not None and len(full_df) > lookback:
        summary_text = _generate_trend_summary(full_df)
        summary_block = f"# 走势概要（全量数据，把握大局）\n\n{summary_text}\n\n---\n\n"
    else:
        summary_block = ""

    return f"""# 股票信息
股票代码: {symbol}
股票名称: {name}
市场状态: {ms}

{summary_block}# 事实数据表格（最近{lookback}个交易日）

{fact_text}

# 图例说明
- 高量列: ★ = 当日为高量柱
- 窗口: 0=高量当日, 1-3=观察窗口, -=过期
- 假K: 假=假阴假阳（K线颜色与实际涨跌方向背离）
- 趋势: ↑上涨 ↓下跌 →震荡
- 量能: 放量/缩量/平量/地量（相对于5日均量）
- 连阳/阴: 连续阳线根数/连续阴线根数
- 绿三: G3 = 绿三兵（连续3天收盘价递减+全部收阴）
- 20d高量: 近20个交易日高量柱出现次数

# 推理提示

请严格按四层递进框架推理：
- 第一层：按方法论四步定位阶段——找SC/BC信号 → 确认阶段 → 判断ST是否通过 → 识别核心矛盾
- 第二层：横向扫描事实表格的量价关系，应用努力与结果法则，给出effort_result
- 第三层：用8项清单逐项打钩评分，输出checklist_score（格式：X/8项末期特征，判定为下跌中继/末期）
- 第四层：构建三条路径+路标，给出最终决策

注意：checklist评分决定决策下限（0-2→清仓/回避，3-5→观望，6-8→机会进场），不要违反。phase必须与checklist评分一致。"""


def parse_llm_response(text: str) -> dict:
    """从LLM响应中解析JSON决策"""
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        text = brace_match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "JSON解析失败", "raw": text[:500]}


def _generate_trend_summary(df: pd.DataFrame) -> str:
    """从全量事实数据生成走势概要，帮助 LLM 把握大局"""
    c = df["close"]
    h = df["high"]
    l = df["low"]
    n = len(df)

    start_date = df.index[0]
    end_date = df.index[-1]
    start_price = c.iloc[0]
    end_price = c.iloc[-1]
    high_price = h.max()
    low_price = l.min()

    lines = []
    lines.append(f"时间范围：{start_date.date()} ~ {end_date.date()}，共{n}个交易日")
    lines.append(f"价格区间：起点{start_price:.2f} → 终点{end_price:.2f}（{(end_price/start_price-1)*100:+.1f}%）")
    lines.append(f"最高价：{high_price:.2f}（{h.idxmax().date()}）")
    lines.append(f"最低价：{low_price:.2f}（{l.idxmin().date()}）")
    lines.append(f"最新收盘：{end_price:.2f}，距最高{(end_price/high_price-1)*100:+.1f}%，距最低{(end_price/low_price-1)*100:+.1f}%")

    trend = df["trend_3bar"]
    phases = []
    phase_start = 0
    for i in range(1, n):
        if trend.iloc[i] != trend.iloc[phase_start]:
            phases.append((trend.iloc[phase_start], df.index[phase_start], df.index[i - 1],
                           c.iloc[phase_start], c.iloc[i - 1]))
            phase_start = i
    phases.append((trend.iloc[phase_start], df.index[phase_start], df.index[-1],
                   c.iloc[phase_start], c.iloc[-1]))

    lines.append(f"\n趋势分段：")
    for t, s, e, sp, ep in phases:
        chg = (ep / sp - 1) * 100
        tag = {"上涨": "↑", "下跌": "↓", "震荡": "→"}.get(t, t)
        lines.append(f"  {s.date()} ~ {e.date()} {tag} {t}（{sp:.1f}→{ep:.1f} {chg:+.1f}%）")

    hv_mask = df["is_high_volume"]
    hv_dates = df.index[hv_mask]
    lines.append(f"\n全量高量柱（共{hv_mask.sum()}次）：")
    for d in hv_dates:
        row = df.loc[d]
        lines.append(f"  {d.date()} 收{row['close']:.1f} {row['volume_state']} "
                     f"实体{row['body_ratio']:.0%} 下影{row['lower_shadow_ratio']:.0%} "
                     f"上影{row['upper_shadow_ratio']:.0%} {row['trend_3bar']}")

    wyckoff_events = []
    for d in df.index:
        row = df.loc[d]
        tags = []
        if row.get("is_SC", False):
            tags.append("SC恐慌抛售")
        if row.get("is_BC", False):
            tags.append("BC抢购高潮")
        if row.get("is_ST", False):
            tags.append("ST二次测试")
        if row.get("is_spring", False):
            tags.append("Spring震仓")
        if row.get("is_SOW", False):
            tags.append("SOW弱势信号")
        if row.get("is_UTAD", False):
            tags.append("UTAD派发假突破")
        if tags:
            wyckoff_events.append(f"  {d.date()} {' + '.join(tags)}")
    if wyckoff_events:
        lines.append(f"\n威科夫关键信号（SC/BC/ST/Spring/SOW/UTAD）：")
        lines.extend(wyckoff_events)
        sc_count = sum(df.get("is_SC", [False]))
        st_count = sum(df.get("is_ST", [False]))
        if sc_count > 0 and st_count > 0:
            lines.append(f"  → 已完成 SC→ST 底部确认链条，供应枯竭得到验证")
        elif sc_count > 0:
            lines.append(f"  → 已出现SC，等待ST二次测试确认底部")

    latest = df.iloc[-1]
    lines.append(f"\n最新（{end_date.date()}）：")
    lines.append(f"  高量柱：{'是' if latest['is_high_volume'] else '否'}")
    lines.append(f"  近20日高量次数：{int(latest['high_vol_count_20d'])}")
    lines.append(f"  连续阳线：{int(latest['consecutive_yang'])}根 / 连续阴线：{int(latest['consecutive_yin'])}根")
    lines.append(f"  当前支撑位：{latest['support_level']:.2f}" if not pd.isna(latest['support_level']) else "  当前支撑位：无")
    lines.append(f"  当前压力区间：{latest['resistance_low']:.2f} ~ {latest['resistance_high']:.2f}" if not pd.isna(latest['resistance_high']) else "  当前压力区间：无")

    # 威科夫关键位
    if "ice_line" in df.columns and not pd.isna(latest.get("ice_line", np.nan)):
        lines.append(f"  冰线(Ice Line)：{latest['ice_line']:.2f}")
    if "in_trading_range" in df.columns:
        in_tr = latest.get("in_trading_range", False)
        if in_tr and not pd.isna(latest.get("trading_range_high", np.nan)):
            pos = latest.get("price_position_in_range", 0.5)
            pos_label = "下沿" if pos < 0.33 else ("中部" if pos < 0.67 else "上沿")
            lines.append(f"  震荡区间：{latest['trading_range_low']:.2f} ~ {latest['trading_range_high']:.2f}（当前在{pos_label} {pos:.0%}）")
        else:
            lines.append(f"  震荡区间：无明确横盘区间")
    if "is_UTAD" in df.columns and latest.get("is_UTAD", False):
        lines.append(f"  [!] 当日出现UTAD(派发假突破)信号")

    if "macd_hist_trend" in df.columns:
        lines.append(f"  MACD状态：DIF={latest.get('macd_dif',0):.2f} DEA={latest.get('macd_dea',0):.2f} 柱趋势={latest.get('macd_hist_trend','?')}")

    return "\n".join(lines)


def run_decision(
    facts_df: pd.DataFrame,
    symbol: str,
    name: str = "",
    lookback: int = 15,
    llm_client=None,
    full_df: pd.DataFrame | None = None,
) -> dict:
    """
    端到端决策：事实层 → LLM推理 → 结构化输出

    Parameters
    ----------
    facts_df : pd.DataFrame
        compute_facts 返回的 DataFrame（已截取最近 lookback 天）
    symbol : str
        股票代码
    name : str
        股票名称
    lookback : int
        事实表格展示最近多少天
    llm_client : LangChain ChatModel or None
        LLM客户端，如不传则自动创建
    full_df : pd.DataFrame or None
        全量事实数据，用于生成走势概要。不传则无概要。

    Returns
    -------
    dict
        包含 phase, effort_result, checklist_score, paths, final_action, summary 等
    """
    if llm_client is None:
        llm_client = _create_default_client()

    system_prompt = build_system_prompt()
    user_prompt = build_decision_prompt(facts_df, symbol, name, lookback=lookback, full_df=full_df)

    response = llm_client.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])

    text = response.content if hasattr(response, "content") else str(response)
    return parse_llm_response(text)


def _create_default_client():
    """从环境变量创建默认LLM客户端，返回 LangChain ChatModel 实例"""
    try:
        from dotenv import load_dotenv
        for env_path in [".env", "../.env", "../../.env"]:
            if os.path.exists(env_path):
                load_dotenv(env_path, override=True)
                break
    except ImportError:
        pass

    from tradingagents.llm_clients.factory import create_llm_client

    provider = os.environ.get("TA_LLM_PROVIDER", "deepseek")
    model = os.environ.get("TA_LLM_DEEP", "deepseek-v4-pro")
    base_url = os.environ.get("TA_BASE_URL", "https://api.deepseek.com/v1")
    api_key = os.environ.get("TA_API_KEY", "")

    client = create_llm_client(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=0.1,
        max_tokens=4096,
    )
    return client.get_llm()
