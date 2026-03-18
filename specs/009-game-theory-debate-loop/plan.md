# Implementation Plan: 009-game-theory-debate-loop

**Goal:** Implement a claim-driven debate between the Smart Money Agent and the Retail Investor Agent to uncover psychological and chip-based discrepancies.

---

### Task 1: Update Agent State
**Files:**
- Modify: `tradingagents/agents/utils/agent_states.py`

- [ ] Add `GameTheoryDebateState` TypedDict (mirroring `InvestDebateState`).
- [ ] Add `game_theory_debate_state` to `AgentState`.

### Task 2: Refactor Analysts into Debators
**Files:**
- Modify: `tradingagents/agents/analysts/smart_money_analyst.py`
- Modify: `tradingagents/agents/analysts/retail_investor_analyst.py`
- Modify: `tradingagents/prompts/zh.py`

- [ ] Update Prompts to support "Responding to claims from the other side".
- [ ] Refactor analyst node logic to handle history and structured claim output (like Bull/Bear).

### Task 3: Setup Graph Loop
**Files:**
- Modify: `tradingagents/graph/conditional_logic.py`
- Modify: `tradingagents/graph/setup.py`

- [ ] Add `should_continue_gt_debate` to `ConditionalLogic`.
- [ ] Connect `Smart Money` and `Retail` nodes in a 1-2 round loop.
- [ ] Ensure the loop terminates and flows into `Game Theory Manager`.

### Task 4: Verification
**Files:**
- Create: `tests/test_gt_debate.py`

- [ ] Verify that Smart Money tries to "influence" retail.
- [ ] Verify that Retail "reacts" to smart money moves.
- [ ] Verify final synthesized output from the Manager.
