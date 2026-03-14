# Agent 架构演进实施计划

本文档对应 [架构提案](/mnt/e/element_workspace/TradingAgents-AShare/docs/design-agent-architecture-evolution.zh-CN.md)，用于指导分阶段实施。目标是把改造拆成 3 个可以独立评审、独立回滚的 PR。

## 总体策略

1. 先铺状态与输入底座，再改辩论逻辑，最后加闭环路由。
2. 每个 PR 都应保证主流程可运行。
3. 每个 PR 都优先采用“并行字段 + 兼容旧字段”的方式，避免一次性替换造成大面积回归。

---

## PR1：状态底座与上下文接线

### 目标

解决“系统不知道当前市场在哪、是否开市、用户有什么持仓与约束”的问题，并修复当前运行时配置没有真正接进图的问题。

### 范围

涉及模块：

- `api/main.py`
- `tradingagents/agents/utils/agent_states.py`
- `tradingagents/graph/propagation.py`
- `tradingagents/graph/trading_graph.py`
- `tradingagents/graph/setup.py`
- `tradingagents/graph/conditional_logic.py`
- 相关 prompt 与前端入参模型

### 改动项

1. 为 `AnalyzeRequest` 增加可选用户上下文字段
   - `objective`
   - `risk_profile`
   - `investment_horizon`
   - `cash_available`
   - `current_position`
   - `current_position_pct`
   - `average_cost`
   - `max_loss_pct`
   - `constraints`
   - `user_notes`

2. 引入状态子结构
   - `instrument_context`
   - `market_context`
   - `user_context`
   - `workflow_context` 的初始占位

3. 系统自动补齐市场元信息
   - `market_country`
   - `exchange`
   - `timezone`
   - `market_session`
   - `market_is_open`
   - `analysis_mode`
   - `data_as_of`

4. 修复配置接线
   - `DEFAULT_CONFIG["max_debate_rounds"]`
   - `DEFAULT_CONFIG["max_risk_discuss_rounds"]`
   - `DEFAULT_CONFIG["max_recur_limit"]`
   应真正传入 `ConditionalLogic` 与 `Propagator`

5. 为不同角色准备 context builder
   - 先不强制全量使用
   - 但要先形成统一入口函数，后续 PR2 直接复用

### 验收标准

1. 请求可以携带用户持仓与约束，且这些字段能出现在最终状态中。
2. 系统能明确写出当前分析模式，例如 `post_market` 或 `t_plus_1`。
3. 修改配置中的辩论轮数后，图行为真的变化。
4. 不传新增字段时，旧接口行为保持兼容。

### 风险

1. API 模型扩展可能影响前端表单和持久化。
2. 不同市场代码规范化逻辑可能需要更清楚的交易所映射规则。

### 建议评审重点

1. 字段命名是否足够稳定。
2. 市场时段计算是否可测试。
3. 新状态是否保持向后兼容。

---

## PR2：辩论引擎与博弈分析升级

### 目标

解决“辩论只是顺序发言”和“多轮后进入复读定式”的问题，并让 Game Theory Manager 的输出变得可结构化消费。

### 范围

涉及模块：

- `tradingagents/agents/utils/agent_states.py`
- `tradingagents/agents/researchers/*.py`
- `tradingagents/agents/risk_mgmt/*.py`
- `tradingagents/agents/managers/research_manager.py`
- `tradingagents/agents/managers/game_theory_manager.py`
- `tradingagents/prompts/zh.py`
- `tradingagents/prompts/en.py`
- `tradingagents/graph/conditional_logic.py`

### 改动项

1. 在辩论状态中引入 claim 级结构
   - `claims`
   - `open_claim_ids`
   - `unresolved_claim_ids`
   - `focus_claim_ids`
   - `round_summary`
   - `round_goal`

2. 升级 Bull/Bear prompt
   - 必须优先回应 `focus_claim_ids`
   - 必须指出反驳对象
   - 必须区分“新 claim”和“对旧 claim 的回应”

3. 升级风控三方 prompt
   - Neutral 不再只是调和
   - 必须识别哪一方提供了有效增量
   - 必须指出尚未解决的执行风险

4. 引入中间摘要逻辑
   - 每轮之后写 `round_summary`
   - 后续轮次不再无脑喂完整历史

5. 升级 Game Theory Manager 输出
   - 至少增加：
     - `players`
     - `board`
     - `likely_actions`
     - `counter_consensus_signal`
     - `confidence`
   - 文本报告继续保留，供现有展示层消费

### 验收标准

1. 多空双方每轮都能明确回应具体 claim。
2. `Research Manager` 能看到未回应 claim，并据此收口。
3. 多轮辩论时，prompt 长度增长得到控制。
4. Game Theory 输出具备可读取的结构化字段。

### 风险

1. 如果 claim 结构设计过重，会增加 prompt 复杂度。
2. Prompt 改动较大，容易出现中英文模板行为不一致。

### 建议评审重点

1. claim 数据结构是否简洁够用。
2. round summary 是否真的减少噪音。
3. 是否避免“只改 prompt、不改状态”的伪升级。

---

## PR3：风控回退闭环与执行约束

### 目标

让 Risk Judge 真正审查 Trader 最终方案，并在必要时带约束打回，形成一次有限闭环。

### 范围

涉及模块：

- `tradingagents/graph/setup.py`
- `tradingagents/graph/conditional_logic.py`
- `tradingagents/agents/managers/risk_manager.py`
- `tradingagents/agents/trader/trader.py`
- `tradingagents/agents/utils/agent_states.py`
- `tradingagents/prompts/zh.py`
- `tradingagents/prompts/en.py`

### 改动项

1. 修正 Risk Judge 输入对象
   - 从 `investment_plan` 改为 `trader_investment_plan`

2. 引入 `risk_feedback_state`
   - `retry_count`
   - `max_retries`
   - `revision_required`
   - `hard_constraints`
   - `latest_risk_verdict`

3. 增加 Risk Judge 条件路由
   - `pass -> END`
   - `revise -> Trader`
   - 达到上限后强制收口

4. Trader 支持消费风险红线
   - 重生成方案时显式纳入：
     - 最大仓位
     - 必须等待的确认条件
     - 强制止损或降风险条件

5. 输出结构化风控裁决
   - `verdict`
   - `hard_constraints`
   - `execution_preconditions`
   - `de_risk_triggers`

### 验收标准

1. Risk Judge 明确审查 Trader 最终方案。
2. 风控否决时，Trader 能收到明确的硬约束并重新生成方案。
3. 循环次数可控，不会死锁。
4. 最终结果中能看出“原方案、风控约束、修订方案”的关系。

### 风险

1. 新闭环可能改变最终耗时。
2. 需要确保前端展示逻辑不会把 revise 误判为失败。

### 建议评审重点

1. 条件路由是否稳定。
2. 是否存在无限重试或状态覆盖错误。
3. Trader 的二次生成是否真正遵循硬约束。

---

## 跨 PR 设计约束

所有 PR 都应遵守以下规则：

1. 保留旧字符串报告字段，直到前端和存储完全适配新结构。
2. 新增结构化字段必须有默认值。
3. 路由变化优先挂在配置开关后，便于灰度。
4. 任何 prompt 升级都必须配套状态字段升级。

---

## 推荐落地顺序

实际执行时，建议顺序如下：

1. 先合 PR1，验证状态扩展和配置接线没有破坏主流程。
2. 再合 PR2，集中处理最关键的“伪辩论”问题。
3. 最后合 PR3，把风控从终点裁决升级为有限闭环。

这个顺序的好处是：

1. PR1 打的是基础，不改变核心行为。
2. PR2 改推理质量，但不引入复杂回退路由。
3. PR3 最后做闭环，便于在已有新状态与新 prompt 基础上稳定落地。

---

## 里程碑检查清单

### 里程碑 A：上下文就位

- 市场元信息进入状态
- 用户持仓与风险约束进入状态
- 配置轮数真正生效

### 里程碑 B：辩论有效

- 存在 claim 级追踪
- 存在未回应分歧列表
- 多轮辩论不再完全依赖长文本历史

### 里程碑 C：风控闭环成立

- Risk Judge 审查 Trader 终稿
- 存在 revise 路径
- 存在重试上限

---

## 补充建议

如果工程节奏允许，可以在 PR2 或 PR3 后追加一个小 PR，用于补测试与可观测性：

1. 为状态初始化与路由条件补单元测试。
2. 为辩论状态输出增加调试日志或开发态可视化。
3. 为 Risk Judge 的 `pass/revise/reject` 结果增加结构化埋点。

这不是第一优先级，但会显著提升后续贡献效率。
