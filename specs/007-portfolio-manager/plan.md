# Implementation Plan: 007-portfolio-manager

**Goal:** Implement the `Portfolio Manager` agent that takes the Risk Judge's verdict and calculates final position sizes and sector-level adjustments based on the user's capital and constraints.

---

### Task 1: Extend Agent State
**Files:**
- Modify: `tradingagents/agents/utils/agent_states.py`

- [ ] Add `portfolio_report` (str) to `AgentState`.
- [ ] Add `allocation_details` (dict) to `AgentState`.

### Task 2: Create Portfolio Manager Agent
**Files:**
- Create: `tradingagents/agents/managers/portfolio_manager.py`

- [ ] Implement `create_portfolio_manager(llm)` node logic.
- [ ] Integrate user capital (`cash_available`) and risk budget calculation.
- [ ] Add sector concentration scoring based on `macro_report`.

### Task 3: Integrate into LangGraph
**Files:**
- Modify: `tradingagents/graph/setup.py`

- [ ] Add `Portfolio Manager` node.
- [ ] Change `Risk Judge`'s `END` edge to point to `Portfolio Manager`.
- [ ] Connect `Portfolio Manager` to `END`.

### Task 4: Verification
**Files:**
- Create: `tests/test_portfolio_manager.py`

- [ ] Verify that high-confidence trades get higher allocations.
- [ ] Verify that user cash constraints are respected.
- [ ] Verify the final report output.
