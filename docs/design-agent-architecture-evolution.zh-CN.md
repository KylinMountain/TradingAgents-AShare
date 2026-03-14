# Agent 架构演进提案：上下文分层、真实辩论与闭环风控

## 1. 背景

当前 TradingAgents-AShare 已经具备完整的多 Agent 主流程：

```text
并行分析师 -> Game Theory Manager -> 多空研究辩论 -> Trader -> 风控辩论 -> Risk Judge
```

从工程完整性看，这条链路是清楚的；但从 Agent 设计质量看，当前系统仍然存在三个核心结构缺陷：

1. **上下文污染**：所有分析结果以全局字符串形式共享，下游 Agent 很容易被前置报告锚定，形成“伪独立”。
2. **伪辩论**：Bull/Bear 与风控三方主要是按固定顺序轮流发言，而非围绕明确议题强制引用、反驳和收敛。
3. **单向流水线**：Trader 和 Risk Judge 缺少真正的反馈闭环，风控更像终点盖章而不是约束执行。

本提案的目标不是推翻现有系统，而是在尽量保留现有 LangGraph 主框架的前提下，把系统从“角色扮演式串行分析”升级为“有上下文边界、有分歧跟踪、有反馈闭环的协作系统”。

---

## 2. 现状确认

以下结论已由当前代码验证。

### 2.1 全局状态过扁平

当前 [agent_states.py](/mnt/e/element_workspace/TradingAgents-AShare/tradingagents/agents/utils/agent_states.py) 中，主状态只显式包含：

- `company_of_interest`
- `trade_date`
- 各分析师报告字符串
- 两个辩论状态字符串

这意味着：

1. 缺少“当前属于哪个市场/国家/交易所”的明确上下文。
2. 缺少“当前是否开市、盘前、盘中、盘后、休市”的运行上下文。
3. 缺少用户持仓、成本、风险预算、目标动作等产品层输入。
4. 缺少分析师私有视角与结构化证据表示。

### 2.2 入口只提取股票与日期

当前 [api/main.py](/mnt/e/element_workspace/TradingAgents-AShare/api/main.py) 的自然语言入口 `_ai_extract_symbol_and_date()` 只抽取：

- `stock_name`
- `date`

用户如果提供如下信息，当前系统都无法可靠进入主状态：

- 当前持仓数量
- 持仓成本
- 可用资金
- 希望加仓/减仓/止损/观察
- 风险偏好
- 持有周期

### 2.3 辩论是“轮换”，不是“对抗”

当前 [conditional_logic.py](/mnt/e/element_workspace/TradingAgents-AShare/tradingagents/graph/conditional_logic.py) 的研究辩论路由依赖：

- `current_response.startswith("Bull")`

风控辩论依赖：

- `latest_speaker.startswith("Aggressive")`
- `latest_speaker.startswith("Conservative")`

这说明路由本身只负责顺序轮换，不负责判断：

- 哪个关键论点尚未回应
- 哪一方需要继续补证
- 辩论是否出现新信息增量
- 辩论是否已经陷入复读

### 2.4 历史累积方式会导致定式化

当前辩论历史是单个不断累积的长字符串。每轮都将整段 `history` 全量喂回模型。轮数一多，容易出现：

1. 有效分歧被淹没在上下文噪音中。
2. 模型复读自己和对手的既有句式。
3. 后续 Agent 无法区分“已解决分歧”和“待解决分歧”。

### 2.5 Game Theory Manager 名称与职责不匹配

当前 [game_theory_manager.py](/mnt/e/element_workspace/TradingAgents-AShare/tradingagents/agents/managers/game_theory_manager.py) 实际上只是读取：

- `smart_money_report`
- `sentiment_report`

然后基于 prompt 输出一段预期差描述。它并没有真正显式建模：

- 局面（Board）
- 参与者（Players）
- 收益结构（Payoffs）
- 可能动作（Action Set）
- 占优策略或脆弱均衡

### 2.6 风控法官尚未形成闭环

当前 `Risk Judge -> END` 是固定边，[setup.py](/mnt/e/element_workspace/TradingAgents-AShare/tradingagents/graph/setup.py) 中没有回退路径。

此外，Risk Judge 当前读取的是 `investment_plan` 而非 Trader 最终产出的 `trader_investment_plan`，这会直接削弱风控裁决的真实性。

---

## 3. 设计目标

本轮演进希望达成以下目标：

1. **让上下文显式化**：市场上下文、用户上下文、分析会话上下文必须进入状态层，而不是散落在 prompt 文字中。
2. **让 Agent 真正分工**：不同角色看到的上下文必须按职责裁剪，而不是共享整块黑板。
3. **让辩论围绕议题展开**：每轮必须回应具体 claim，而不是自由发挥。
4. **让系统有反馈闭环**：Risk Judge 在拒绝执行时，应能附带硬约束打回 Trader。
5. **让博弈分析名副其实**：若继续使用 “Game Theory Manager” 名称，则输出必须结构化地表达参与者、动作和预期差。
6. **控制改造风险**：优先增量演进，不一次性重写全部 Agent。

非目标：

1. 本轮不引入 RL、策略回测闭环或训练级别改造。
2. 本轮不要求每个分析师都变成工具可回调的专家服务，但状态与接口设计要为后续演进留口。

---

## 4. 提议中的新状态模型

### 4.1 状态分层原则

将当前扁平状态改为四层：

1. **Instrument Context**：标的信息本身
2. **Market Context**：市场环境与交易时序
3. **User Context**：用户持仓与约束
4. **Workflow Context**：本次会话内部的辩论、决策与反馈状态

### 4.2 建议的数据结构

```python
class InstrumentContext(TypedDict):
    symbol: str
    security_name: str
    market_country: str
    exchange: str
    currency: str
    asset_type: str


class MarketContext(TypedDict):
    trade_date: str
    timezone: str
    market_session: str         # pre_open / open / lunch_break / post_close / closed
    market_is_open: bool
    analysis_mode: str          # pre_market / intraday / post_market / t_plus_1
    data_as_of: str
    session_note: str


class UserContext(TypedDict, total=False):
    objective: str              # 建仓 / 加仓 / 减仓 / 止损 / 观察
    risk_profile: str           # 保守 / 平衡 / 激进
    investment_horizon: str     # 日内 / 短线 / 波段 / 中线
    cash_available: float
    current_position: float
    current_position_pct: float
    average_cost: float
    max_loss_pct: float
    constraints: list[str]
    user_notes: str


class ClaimRecord(TypedDict):
    claim_id: str
    speaker: str
    stance: str
    claim: str
    evidence: list[str]
    target_claim_id: str | None
    rebuttal_of: str | None
    confidence: float
    novelty_score: float
    status: str                 # open / addressed / unresolved / accepted / rejected


class DebateRoundState(TypedDict):
    round_index: int
    focus_claim_ids: list[str]
    round_goal: str
    round_summary: str
    new_claims: list[ClaimRecord]


class InvestDebateState(TypedDict):
    rounds: list[DebateRoundState]
    claims: list[ClaimRecord]
    open_claim_ids: list[str]
    unresolved_claim_ids: list[str]
    accepted_claim_ids: list[str]
    current_speaker: str
    current_response: str
    count: int


class RiskFeedbackState(TypedDict):
    retry_count: int
    max_retries: int
    revision_required: bool
    hard_constraints: list[str]
    latest_risk_verdict: str
```

### 4.3 为什么要这样拆

这样做的价值不只是“更规范”，而是直接解决当前误导问题：

1. 市场归属、交易时段和数据时效性不再靠模型猜。
2. 用户持仓与目标动作成为结构化输入，不再在 prompt 里隐形丢失。
3. 分歧从“长文本”变成“可追踪 claim”，后续路由才有机会按未解决问题推进。

---

## 5. Agent 输入合同重构

### 5.1 原则

不是所有 Agent 都应该看到同样的信息。

建议引入“上下文裁剪层”，为不同角色构造不同输入视图。

### 5.2 建议的职责边界

#### 分析师层

分析师默认只拿：

- `InstrumentContext`
- `MarketContext`
- 与自己相关的工具结果
- 必要的用户目标摘要，但不拿完整持仓细节

原因：

1. 避免用户仓位成本污染市场分析。
2. 避免分析师为了迎合用户已有仓位而输出偏见结论。

#### Research / Game Theory / Research Manager

研究层拿：

- 所有分析师的结构化输出
- Claim 状态
- 精简版用户目标

不直接看过多交易执行约束，避免研究与执行混淆。

#### Trader / Risk Judge

交易与风控层额外拿：

- 完整 `UserContext`
- 已有仓位和成本
- 风险红线
- 市场时段和执行可行性

这样 Trader 才能判断“是建仓建议还是持仓处理建议”，Risk Judge 才能判断“当前方案对这个用户是否可执行”。

---

## 6. 辩论机制重构：从长文本轮换到 Claim 驱动

### 6.1 当前问题

虽然当前 prompt 要求“逐点反驳”，但架构上并没有强制。

结果是：

1. 模型可以选择性忽视对方关键论点。
2. 管理层无法知道哪些分歧真正被回应。
3. 辩论轮数提升后，上下文膨胀会降低有效信息密度。

### 6.2 新机制

每轮辩论必须满足以下合同：

1. **引用**：先点名回应一个指定 `claim_id`
2. **反驳**：必须说明反驳的是哪条证据或哪一个脆弱假设
3. **补证**：若要提出新观点，必须附证据和置信度
4. **产出结构化摘要**：输出中除了自然语言正文，还要附带 claim 级摘要

### 6.3 Prompt 约束升级

新的 Bull/Bear prompt 应硬约束为：

1. 先回应 `focus_claim_ids`
2. 若未回应指定 claim，输出无效
3. 不允许只复述立场，必须给出证据增量或逻辑击穿
4. 每轮最多新增有限数量的新 claim，控制信息膨胀

### 6.4 辩论循环中的“破局变量”

为解决“5轮后进入定式”的问题，引入三个新变量：

1. `round_goal`
   - 例如：本轮只讨论“为什么是现在买”或“该策略的最大回撤路径”
2. `focus_claim_ids`
   - 本轮只允许围绕少量高影响 claim 展开
3. `novelty_score`
   - 若连续两轮新增信息过少，Research Manager 或 Risk Judge 可提前收口

### 6.5 中间摘要器

在多轮辩论中增加一个轻量级 summarizer：

- 输入：最近一轮新增 claim + 当前 open / unresolved claim
- 输出：新的 `round_summary`

这样后续轮次不再反复读全量历史，而是读：

- 当前轮摘要
- 待解决分歧
- 对手上一轮回应

---

## 7. Game Theory Manager 重构

### 7.1 两条可选路线

#### 路线 A：保留名称，真正做博弈论视角建模

输出改为结构化对象：

```python
class GameTheoryView(TypedDict):
    board: str
    players: list[str]
    player_states: dict[str, str]
    likely_actions: dict[str, list[str]]
    payoff_map: dict[str, str]
    dominant_strategy: str
    fragile_equilibrium: str
    counter_consensus_signal: str
    confidence: float
```

核心问题必须覆盖：

1. 当前局面是什么？
2. 主力、游资、量化、散户分别处于什么状态？
3. 谁在主动，谁在被动？
4. 当前价格区间里，哪一方的 payoff 更不对称？
5. 哪种预期差最可能被市场交易？

#### 路线 B：承认其是整合层，改名为“预期差分析经理”或“综合分析经理”

如果短期不准备做完整博弈建模，应该尽快更名，避免误导贡献者和用户。

### 7.2 本提案建议

建议保留 `Game Theory Manager` 名称，但第一阶段只做“弱结构化升级”：

1. 先把输出改成结构化字段
2. 先聚焦：
   - 玩家识别
   - 当前局面
   - 下一步最可能行为
   - 反共识信号强度

之后再逐步扩展到完整 payoff 与策略空间。

---

## 8. 产品输入升级：让系统知道用户是谁、市场在哪、此刻是什么时段

### 8.1 需要纳入状态的产品输入

建议将用户输入划分为三类。

#### A. 高价值且可靠，应该进入主状态

- 股票代码
- 交易日期
- 用户目标动作：建仓 / 加仓 / 减仓 / 止损 / 观察
- 当前持仓数量或仓位比例
- 持仓成本
- 可用资金
- 风险偏好
- 持有周期
- 禁止行为约束

#### B. 高价值但可能不可靠，应进入状态但标记来源

- 用户自述理由
- 主观判断
- 自己的止损计划
- 对政策或新闻的理解

这些应带 `source=user_claim` 标签，不能与市场事实混为一谈。

#### C. 不应直接进入主推理链，或只能用于展示

- 纯情绪表达
- 与标的无关的个人背景
- 无法验证的群聊消息

### 8.2 市场元信息必须由系统补齐

系统应自动写入：

- `market_country`
- `exchange`
- `timezone`
- `market_session`
- `market_is_open`
- `analysis_mode`
- `data_as_of`

这会直接影响 agent 的行为。例如：

1. 盘前不应把龙虎榜当成“今天新出的数据”。
2. 盘中分析需要明确区分“截至当前时刻的数据”与“昨日收盘后数据”。
3. T+1 模式下，Smart Money 分析的权重可上升。

---

## 9. 风控闭环设计

### 9.1 目标

让 Risk Judge 从“记录风险”变成“约束执行”。

### 9.2 新的路由逻辑

```text
Risk Debate -> Risk Judge
  -> pass   -> END
  -> revise -> Trader
```

其中：

- `revise` 必须附带 `hard_constraints`
- `retry_count` 超过上限后强制收口

### 9.3 风控裁决结构

建议 Risk Judge 输出：

```python
class RiskJudgeResult(TypedDict):
    verdict: str                # pass / revise / reject
    summary: str
    hard_constraints: list[str]
    soft_constraints: list[str]
    target_price: str
    stop_loss_price: str
    execution_preconditions: list[str]
    de_risk_triggers: list[str]
```

并明确审查对象为：

- `trader_investment_plan`

而不是研究经理的 `investment_plan`。

---

## 10. 推荐的渐进式实施路径

本提案不建议一次性改完全部模块，而是分三步推进：

1. **PR1：状态与上下文底座**
   - 接入 `MarketContext`、`UserContext`
   - 接好运行时配置
   - 让系统知道市场时段与用户持仓
2. **PR2：辩论与博弈层升级**
   - 引入 claim 驱动辩论状态
   - 升级 Bull/Bear 与风控 prompt
   - 让 Game Theory 输出结构化结果
3. **PR3：风控回退闭环**
   - Risk Judge 审 Trader 最终方案
   - 增加 revise 路径和重试上限

---

## 11. 向后兼容策略

为了降低风险，建议遵循以下兼容原则：

1. 新字段全部提供默认值，避免老接口直接崩溃。
2. 老的字符串报告先继续保留，新增结构化字段与之并行存在。
3. 新路由先由配置开关控制，允许逐步灰度。
4. Prompt 与状态一起演进，避免只改 prompt 不改状态造成假升级。

---

## 12. 成功标准

本轮架构演进的验收不应只看“能不能跑通”，而应至少检查：

1. 系统能否明确识别当前市场归属、交易时段和分析模式。
2. 用户持仓、成本和风险约束能否稳定传到 Trader 与 Risk Judge。
3. Bull/Bear 是否能显式追踪未回应 claim。
4. 多轮辩论时，是否能避免简单复读并保持信息增量。
5. Risk Judge 是否能基于 Trader 最终方案触发带约束的打回。
6. Game Theory Manager 的输出是否从散文变成可消费的结构化信号。

---

## 13. 总结

这次演进的本质不是“再多加几个 Agent”，而是把系统的协作逻辑从：

- 共享黑板
- 长文本轮换
- 单向串行

升级为：

- 分层上下文
- claim 驱动对抗
- 约束可回退闭环

如果只做其中最关键的两件事，也应优先做：

1. **上下文分层与用户输入入状态**
2. **辩论从字符串历史改为 claim 与焦点驱动**

这两项完成后，后续无论是风控闭环、分析师按需查询，还是更强的博弈建模，都会进入一个更健康的工程轨道。
