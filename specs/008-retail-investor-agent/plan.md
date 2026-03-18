# Implementation Plan: 008-retail-investor-agent

**Goal:** Implement the `Retail Investor Analyst` that models impulsive retail sentiment and hype, providing the "Crowd View" for the Game Theory Layer.

---

### Task 1: Extend Agent State
**Files:**
- Modify: `tradingagents/agents/utils/agent_states.py`

- [x] Add `retail_report` (str) to `AgentState`.

### Task 2: Implement Agent & Prompt
**Files:**
- Create: `tradingagents/agents/analysts/retail_investor_analyst.py`
- Modify: `tradingagents/prompts/zh.py`

- [x] Add `retail_investor_system_message` to `PROMPTS`.
- [x] Implement `create_retail_investor_analyst` (ReAct loop).
- [x] Export via `tradingagents/agents/__init__.py`.

### Task 3: Integrate into LangGraph
**Files:**
- Modify: `tradingagents/graph/conditional_logic.py`
- Modify: `tradingagents/graph/setup.py`

- [x] Add `should_continue_retail` to `ConditionalLogic`.
- [x] Add `Retail Investor Analyst` to `GraphSetup`.
- [x] Route it to `Game Theory Manager`.

### Task 4: Verification
**Files:**
- Create: `tests/test_retail_analyst.py`

- [x] Verify tool usage (`get_zt_pool`, `get_hot_stocks_xq`).
- [x] Verify sentiment classification (Greed/Fear).
