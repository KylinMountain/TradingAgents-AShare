# 数据时间维度优化待处理需求

## 背景

当前系统在处理盘中实时数据与历史数据时，存在时间维度不一致的问题，需要在分析时明确区分数据的时间状态。

---

## 待处理需求

### 1. Market Analyst 中 stock_data 与 indicators 时间维度不一致

**问题描述：**
- `market_analyst.py` 使用 `stock_data`（包含当日盘中实时K线）和 `indicators`（仅到昨日收盘）
- `stock_data` 最后一行：今日 open/high/low/close(当前价)/volume(部分成交量)
- `indicators` (boll/rsi/macd/sma)：基于昨日收盘价计算，不含今日数据
- LLM 分析时无法区分两者的时间边界，可能误判"价格突破布林带"等信号

**影响范围：**
- [market_analyst.py](../tradingagents/agents/analysts/market_analyst.py) - 市场技术分析

**优化方案：**
在 prompt 中注入时间状态标注：
```python
if current_date == datetime.now().strftime("%Y-%m-%d"):
    intraday_note = (
        f"\n⚠️ 数据说明：stock_data 最后一行为今日（{current_date}）盘中实时数据（未收盘），"
        "但所有技术指标均基于昨日收盘价计算，不含今日数据。"
        "分析时请勿将今日盘中价格与指标值做直接比较，指标信号以昨日收盘为准。\n"
    )
```

**优先级：** 高
**状态：** 待实现

**备注：** 此问题仅存在于 `market_analyst`，`smart_money_analyst` 不使用 `stock_data`，无此问题。

---

### 2. 近5日主力资金净流向盘中数据标注

**问题描述：**
- `get_individual_fund_flow` 返回近5日主力资金数据
- 如果当前是盘中时段，最后一条数据可能是今日的部分数据（非全天）
- 需要验证 akshare 接口在盘中是否返回今日数据，以及数据是否完整

**影响范围：**
- [cn_akshare_provider.py:get_individual_fund_flow](../tradingagents/dataflows/providers/cn_akshare_provider.py) (line ~700)
- [smart_money_analyst.py](../tradingagents/agents/analysts/smart_money_analyst.py)

**验证步骤：**
1. 在开盘时段（9:30-15:00）调用 `akshare.stock_individual_fund_flow()`
2. 检查返回数据的最后一条日期是否为今日
3. 对比盘中数据与收盘后数据的差异

**优化方案：**
如果接口返回今日盘中数据，需在输出中标注：
```python
if last_date == today and is_trading_hours():
    note = "⚠️ 最后一条为今日盘中数据（未收盘），资金流向数据不完整"
```

**优先级：** 中
**状态：** 待验证数据特性

---

### 3. 龙虎榜与行业数据的时间边界处理

**问题描述：**
- 龙虎榜数据 (`get_lhb_detail`) 和行业资金流向 (`get_board_fund_flow`) 当前使用 `current_date` 作为查询日期
- 需要验证这些接口在盘中是否包含今日数据
- 如果是盘前分析（9:30前），应该取上一交易日数据，而非今日

**影响范围：**
- [cn_akshare_provider.py:get_lhb_detail](../tradingagents/dataflows/providers/cn_akshare_provider.py) (line ~730)
- [cn_akshare_provider.py:get_board_fund_flow](../tradingagents/dataflows/providers/cn_akshare_provider.py) (line ~765)
- [smart_money_analyst.py](../tradingagents/agents/analysts/smart_money_analyst.py)
- [sector_analyst.py](../tradingagents/agents/analysts/sector_analyst.py)

**验证步骤：**
1. 在盘前（9:30前）调用接口，查看是否返回今日数据
2. 在盘中（9:30-15:00）调用接口，查看是否返回今日数据
3. 在盘后（15:00后）调用接口，查看数据更新时间点

**优化方案：**
根据当前时间智能选择查询日期：
```python
from datetime import datetime, time

def get_query_date(current_date: str) -> str:
    """根据当前时间返回合适的查询日期"""
    now = datetime.now()
    today = now.date()

    # 如果是盘前（9:30前），使用上一交易日
    if now.time() < time(9, 30):
        return get_previous_trading_day(current_date)

    # 盘中和盘后使用当日
    return current_date
```

**优先级：** 中
**状态：** 待开盘验证数据特性

---

## 验证计划

### 阶段1：数据特性验证（开盘日进行）

在下一个交易日的不同时段运行测试脚本，记录数据特性：

```bash
# 盘前（9:00）
python tests/test_smart_money_data.py all 600519 > logs/premarket_data.log

# 盘中（10:30）
python tests/test_smart_money_data.py all 600519 > logs/intraday_data.log

# 盘后（15:30）
python tests/test_smart_money_data.py all 600519 > logs/aftermarket_data.log
```

### 阶段2：分析优化实现

根据验证结果，实现对应的优化方案：
1. 在 prompt 中添加时间状态标注
2. 在数据输出中添加盘中数据警告
3. 实现智能日期选择逻辑

### 阶段3：回归测试

确保优化后的分析结果更准确，不会误判盘中临时信号。

---

## 相关文件

- [tests/test_smart_money_data.py](../tests/test_smart_money_data.py) - Smart Money 数据源测试脚本
- [docs/analysts/smart_money_analyst.md](./analysts/smart_money_analyst.md) - Smart Money Analyst 文档
- [AKSHARE_ISSUES_SUMMARY.md](../tests/AKSHARE_ISSUES_SUMMARY.md) - AKShare 接口问题汇总

---

**创建时间：** 2026-04-11
**最后更新：** 2026-04-11
