# Intent-Driven Multi-Horizon Trading Analysis — 设计文档

**日期**：2026-03-12
**状态**：待实现
**背景**：量化专家反馈——agents 决策过程不可见；金融市场维度高，短线（1-2天）和中线（1-3月）结论完全不同，需要对问题分类并分维度输出。

---

## 1. 问题陈述

现有架构的三个核心缺陷：

1. **意图盲区**：用户输入的自然语言只用来提取股票代码，"重点看量价"、"判断能否到目标位"等具体意图被忽略。
2. **时间维度缺失**：所有 agent 使用固定回看窗口（market analyst 固定 30 天），无论用户关注的是明天还是三个月后，分析逻辑完全相同。
3. **决策过程不透明**：用户只能看到最终结论，每个 agent 的推理链（用了哪些数据、得出什么关键发现）不可见。

---

## 2. 设计目标

- **意图驱动**：自然语言输入经 IntentParser 解析为结构化意图，贯穿整个 pipeline
- **双视角默认输出**：每次分析默认同时输出短线（1-2周）和中线（1-3月）两个独立结论
- **数据共享，推理分叉**：数据采集层跑一次（90天全量），两个子图按需截取时间窗口
- **推理链可见**：每个 agent 节点输出结构化 trace，前端渲染推理链卡片

---

## 3. 整体架构

```
用户自然语言输入
        ↓
  【IntentParser】          新增，quick_thinking_llm，在 propagate() 调用前执行
  输出: ticker + horizons + focus_areas + specific_questions
        ↓
  【DataCollector】         新增，统一采集 90 天全量数据，存入内存缓存（非 AgentState）
  输出: data_cache[job_id]（stock_data, indicators, news, fundamentals, fund_flow, lhb）
        ↓
  asyncio.gather(短线子图, 中线子图)   ← 两次独立的 graph.invoke()，并发执行
  ┌──────────────────┐  ┌──────────────────┐
  │   短线子图        │  │   中线子图        │
  │  取最近 7-14 天   │  │  取全部 90 天     │
  │                  │  │                  │
  │ market           │  │ fundamentals     │
  │ smart_money      │  │ macro            │
  │ social           │  │ market           │
  │ fundamentals(降权)│  │ smart_money(降权) │
  │ macro(降权)      │  │ social(降权)     │
  │ game_theory      │  │ game_theory(降权) │  ← game_theory 在各自子图的 analysts 完成后运行
  │                  │  │                  │
  │ bull/bear 辩论   │  │ bull/bear 辩论   │
  │ research manager │  │ research manager │
  │ trader           │  │ trader           │
  │ risk debate      │  │ risk debate      │
  │ risk manager     │  │ risk manager     │
  └──────────────────┘  └──────────────────┘
        ↓                        ↓
   短线结论卡片 + 推理链    中线结论卡片 + 推理链
                  （并排展示，不合并）
```

**并行实现方式**：不重构 LangGraph 图结构，而是在 `TradingAgentsGraph.propagate()` 中用 `asyncio.gather` 并发调用两次 `graph.ainvoke()`，每次传入不同的 `horizon` 上下文。两个子图复用同一个已编译的 graph 对象，各自持有独立的 `AgentState` 实例。

**data_cache 设计**：数据不存入 `AgentState`（避免 LangGraph checkpoint 膨胀），而是存在 `TradingAgentsGraph` 实例的内存字典 `self.data_cache: Dict[str, DataPool]` 中，以 `job_id` 为键。各 agent 通过闭包访问 cache，按 horizon 截取所需时间窗口。

---

## 4. IntentParser

**位置**：pipeline 第一个节点
**使用模型**：`quick_thinking_llm`（够用且省成本）

**System Prompt**：
```
你是交易意图解析器。从用户输入中提取以下字段，以 JSON 格式输出，不要输出其他内容：
- ticker: 股票代码（字符串）
- horizons: 时间维度列表，可选值 "short"（1-2周）、"medium"（1-3月），默认 ["short", "medium"]
- focus_areas: 用户特别关注的分析维度列表（字符串数组，可为空）
- specific_questions: 用户的具体问题列表（字符串数组，可为空）
```

**输出示例**：
```json
{
  "ticker": "600519",
  "horizons": ["short", "medium"],
  "focus_areas": ["量价关系", "主力资金"],
  "specific_questions": ["短期能否到+30%目标位"]
}
```

**AgentState 新增字段**：
```python
"user_intent": {
    "raw_query": str,
    "ticker": str,
    "horizons": List[str],       # ["short", "medium"]
    "focus_areas": List[str],
    "specific_questions": List[str],
}
```

---

## 5. DataCollector

**位置**：IntentParser 之后，两个子图之前
**职责**：统一采集所有数据源，存入 `data_pool`，各 agent 不再自行调工具

**采集内容**（固定 90 天全量）：
```python
"data_pool": {
    "stock_data": ...,        # 90天K线 OHLCV
    "indicators": {           # 90天所有技术指标
        "close_50_sma": ...,
        "close_200_sma": ...,
        "close_10_ema": ...,
        "rsi": ...,
        "macd": ...,
        "boll": ..., "boll_ub": ..., "boll_lb": ...,
        "atr": ...,
        "vwma": ...,
    },
    "news": ...,              # 90天新闻
    "global_news": ...,       # 90天宏观新闻
    "fundamentals": ...,      # 财报（不分时间窗口）
    "balance_sheet": ...,
    "cashflow": ...,
    "income_statement": ...,
    "fund_flow_board": ...,   # 90天板块资金流
    "fund_flow_individual": ..., # 90天个股资金流
    "lhb": ...,               # 龙虎榜
    "insider_transactions": ...,
}
```

**子图如何截取**：
- 短线子图：从 `data_pool` 中取最近 7-14 天的数据切片传给 agent
- 中线子图：直接传完整的 `data_pool`

---

## 6. Horizon Context 注入

每个 agent 的 system prompt 开头统一注入 context block：

```
【分析视角】
当前分析维度：{短线（1-2周） | 中线（1-3月）}
用户重点关注：{focus_areas}
具体问题：{specific_questions}

请基于以上视角调整分析重点和结论深度。
```

**各 agent 在不同 horizon 的权重差异**：

| Agent | 短线子图 | 中线子图 |
|-------|---------|---------|
| market | 高权重，看短期技术信号 | 中权重，看中期趋势 |
| smart_money | 高权重 | 低权重，仅看大方向 |
| social | 高权重 | 低权重，仅作参考 |
| game_theory | 高权重 | 低权重 |
| fundamentals | 低权重，仅看关键风险 | 高权重，完整分析 |
| macro | 低权重，仅看近期政策冲击 | 高权重，板块轮动 |

权重通过 system prompt 中的文字指示实现（"本轮分析中你的分析为次要参考维度，简要输出即可"），不需要修改 graph 结构。

---

## 7. Trace 输出（决策过程可见）

每个 analyst agent 在返回 report 的同时，额外输出结构化 trace：

```python
"agent_traces": [
    {
        "agent": "market_analyst",
        "horizon": "short",
        "data_window": "7天",
        "key_finding": "RSI 超买区间 + MACD 顶背离，短线压力明显",
        "verdict": "看空",
        "confidence": "中",  # 高/中/低
    },
    ...
]
```

**AgentState 新增字段**：
```python
"short_term_traces": List[TraceItem]
"medium_term_traces": List[TraceItem]
```

前端用 trace 渲染推理链卡片，用户无需点开完整报告即可看到每个 agent 的核心判断。

---

## 8. 最终输出结构

```python
"short_term_result": {
    "verdict": "看空",
    "confidence": "中",
    "target_price": None,
    "stop_loss": "21.80",
    "core_reasons": ["RSI超买+MACD顶背离", "主力净流出3日", "散户情绪过热"],
    "invalidation": "放量突破前高则止损观点",
    "traces": [...],
    "full_report": "...",   # 点击展开
}

"medium_term_result": {
    "verdict": "看多",
    "confidence": "高",
    "target_price": "26.50",
    "stop_loss": "20.00",
    "core_reasons": ["估值合理现金流健康", "板块资金轮动进入期", "中期均线支撑有效"],
    "invalidation": "季报净利润低于预期20%则重新评估",
    "traces": [...],
    "full_report": "...",   # 点击展开
}
```

前端并排展示两张卡片，不提供合并结论，用户自行决策。

---

## 9. 对现有代码的影响

| 模块 | 变更类型 | 说明 |
|------|---------|------|
| `AgentState` | 新增字段 | `user_intent`, `horizon`, `short_term_traces`, `medium_term_traces` |
| `graph/trading_graph.py` | 修改 | `propagate()` 接收 `query` 参数；新增 `self.data_cache`；`asyncio.gather` 并发两次 `graph.ainvoke()`；`_log_state()` 改写以适配新输出结构 |
| `graph/setup.py` | 小改 | IntentParser、DataCollector 作为独立函数（非 LangGraph 节点）；graph 结构不变，各 analyst 节点从 closure 读 data_cache |
| 各 analyst agent | 修改 | 从 `data_cache` 取数据而非自调工具；输出 trace 字段；接收 horizon context block |
| `prompts/zh.py` | 新增 | IntentParser prompt；各 agent 的 horizon context 模板 |
| API `POST /v1/analyze` | 修改 | 接收 `query` 自然语言字段（替代 `symbol`，兼容旧 `symbol`）；返回 `short_term_result` + `medium_term_result` |
| SSE 事件流 | 修改 | 每个 agent 事件新增 `horizon` 字段（`"short"` \| `"medium"`），前端区分渲染到对应视角面板 |

**已知限制（本期不解决）**：
- `FinancialSituationMemory` 不区分 horizon，两个子图共享同一份记忆库；短期影响可接受，后续迭代中按 horizon 分库
- LHB（龙虎榜）和 `get_individual_fund_flow` 数据源返回固定窗口，DataCollector 直接取最大可用范围，不强制 90 天
- IntentParser 解析失败时（JSON 格式错误或无法识别 ticker），fallback 到旧逻辑：要求用户明确提供 symbol

---

## 10. 暂不涉及

- 超短线维度（1-3天）：可作为后续迭代，在 IntentParser 中识别后激活
- 长线维度（3月+）：同上
- 用户持仓信息输入（成本价、仓位比例）
- 多标的同时分析
- 自动下单

---

## 11. 成功标准

1. 用户自然语言输入被完整解析，focus_areas 和 specific_questions 在最终报告中得到回应
2. 短线和中线结论在市场分歧时能输出不同方向（不会永远一致）
3. 每个 agent 的推理链在前端可见，用户无需阅读完整报告即可理解决策逻辑
4. 整体分析延迟相比现有版本增幅不超过 50%（数据共享是关键）
