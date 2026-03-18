# Ecosystem Agent Implementation Plan (Phase 2)

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the "Ecosystem Domino Analyst" that autonomously queries competitors and supply chain entities for a given ticker and analyzes the collective data to validate the target stock's logical narrative.

**Architecture:** 
1. Create new tools to fetch a stock's industry peers/competitors.
2. Create `EcosystemAnalyst` as a LangGraph node.
3. Hook `EcosystemAnalyst` into the main parallel analyst fan-out.

**Tech Stack:** Python, LangGraph, AkShare.

---

### Task 1: Create Ecosystem Data Tools

**Files:**
- Modify: `tradingagents/agents/utils/agent_utils.py`
- Test: `tests/test_ecosystem_tools.py`

- [ ] **Step 1: Write test for `get_industry_peers` tool**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `get_industry_peers` tool**
  (For simplicity, we will mock or use a lightweight static mapping/Akshare industry query if available. We will implement a basic version that returns 2-3 related tickers.)
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

### Task 2: Create Ecosystem Analyst Agent

**Files:**
- Create: `tradingagents/agents/analysts/ecosystem_analyst.py`
- Modify: `tradingagents/prompts/zh.py`

- [ ] **Step 1: Add `ecosystem_system_message` to prompts**
- [ ] **Step 2: Implement `create_ecosystem_analyst` logic**
  (Similar to `SmartMoneyAnalyst`, it should have a ReAct loop. It will call `get_industry_peers`, then potentially call `get_news` on those peers).
- [ ] **Step 3: Commit**

### Task 3: Integrate into LangGraph

**Files:**
- Modify: `tradingagents/graph/conditional_logic.py`
- Modify: `tradingagents/graph/setup.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Modify: `api/main.py` (Add to `selected_analysts` defaults and tool descriptions)

- [ ] **Step 1: Add `should_continue_ecosystem` to `ConditionalLogic`**
- [ ] **Step 2: Add to `_create_tool_nodes` and `GraphSetup`**
- [ ] **Step 3: Commit**

### Task 4: E2E Verification

**Files:**
- Create: `tests/test_e2e_ecosystem.py`

- [ ] **Step 1: Write E2E test verifying Ecosystem Agent runs**
- [ ] **Step 2: Execute test and verify report output**
- [ ] **Step 3: Commit**