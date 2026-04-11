# 主力资金分析师 (Smart Money Analyst)

## 角色定位

追踪主力资金动向，通过资金流向、龙虎榜和成交量指标判断机构/大资金行为。

## 时间视角

固定**短期**（short）

## 数据源详解

### 1. 主力资金净流向 (`get_individual_fund_flow`)

**输入参数：**
- `symbol`: 股票代码（如 "600519"）

**底层采集接口：**
```python
akshare.stock_individual_fund_flow(stock=code, market=market)
# market: "sh"（沪市：5/6/9开头）或 "sz"（深市）
```

**数据来源：** 东方财富网个股资金流向

**输出格式：**
```
600519 近5日主力资金净流向：
     日期    主力净流入   超大单净流入   大单净流入   中单净流入   小单净流入
2026-04-07  -1234.56    -800.00      -434.56     500.00      734.56
...
```

**数据窗口：** 最近5个交易日

---

### 2. 龙虎榜明细 (`get_lhb_detail`)

**输入参数：**
- `symbol`: 股票代码
- `date`: 查询日期（格式：YYYY-MM-DD）

**底层采集接口：**
```python
akshare.stock_lhb_detail_em(start_date=date_fmt, end_date=date_fmt)
# date_fmt: "20260407" (去掉横杠)
# 返回全市场数据，代码内手动过滤指定股票
```

**数据来源：** 东方财富网龙虎榜

**输出格式：**
```
600519 龙虎榜明细（2026-04-07）：
代码    名称    上榜原因    买入金额    卖出金额    净买入    营业部
600519  贵州茅台  日涨幅偏离值达7%  5000.00    2000.00    3000.00   机构专用
...
```

**特殊情况：** 非异动日无数据属正常（返回"无龙虎榜数据"）

---

### 3. 成交量指标 (`get_indicators` - vwma)

**输入参数：**
- `symbol`: 股票代码
- `indicator`: "volume"
- `curr_date`: 当前日期
- `look_back_days`: 20（回溯天数）

**底层采集接口：**
```python
# 通过 yfinance 获取15年历史日K数据
yfinance.download(ticker, start=start_date, end=end_date)
# 然后计算 vwma (Volume Weighted Moving Average)
```

**数据来源：** Yahoo Finance（通过 yfinance）

**输出格式：**
```
2026-03-18: 12345678.90
2026-03-19: 13456789.01
...
2026-04-07: 14567890.12
```

**数据窗口：** 近20个交易日的成交量加权均线

---

## 数据流向

```
┌─────────────────────────────────────────┐
│  smart_money_analyst_node               │
│  输入: state (ticker, current_date)     │
└─────────────────┬───────────────────────┘
                  │
                  ├─ 优先从 data_collector 缓存读取
                  │  pool["fund_flow_individual"]
                  │  pool["lhb"]
                  │  pool["indicators"]["vwma"]
                  │
                  ├─ 缓存未命中 → 并行调用3个工具
                  │  ├─ get_individual_fund_flow(symbol)
                  │  ├─ get_lhb_detail(symbol, date)
                  │  └─ get_indicators(symbol, "volume", date, 20)
                  │
                  ├─ 构建 Prompt
                  │  ├─ SystemMessage: smart_money_system_message
                  │  └─ HumanMessage: horizon_ctx + 3个数据块
                  │
                  ├─ LLM 流式生成分析报告
                  │  └─ Token级实时输出到 tracker
                  │
                  └─ 提取 verdict + confidence
                     └─ 返回 smart_money_report + analyst_traces
```

## 分析逻辑

1. 并行获取主力资金流向 + 龙虎榜 + vwma 指标
2. 结合用户意图构建 horizon 上下文
3. 调用 LLM 生成主力资金分析报告（`smart_money_report`）
4. 提取 `verdict` 和 `confidence`

## 输出结构

### `smart_money_report` (str)
LLM 生成的完整主力资金分析报告（中文），包含：
- 资金流向解读
- 龙虎榜席位分析
- 成交量异常判断

### `analyst_traces` (list)
```python
[{
    "agent": "smart_money_analyst",
    "horizon": "short",
    "data_window": "近期可用",
    "key_finding": "主力资金分析结论：看多/看空/中性",
    "verdict": "看多/看空/中性",
    "confidence": 0.75  # 0-1之间
}]
```

## 关键特性

- **并行获取**：3个数据源异步并发调用，提升速度
- **缓存优先**：优先使用 data_collector 预取的数据，减少重复请求
- **容错处理**：单个数据源失败返回"无数据"，不阻断整体分析
- **流式输出**：Token级实时流式输出到前端，提升用户体验
