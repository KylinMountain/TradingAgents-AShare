# Implementation Plan: 010-portfolio-gt-integration

**Goal:** Inject structured Game Theory signals into the Portfolio Manager to enable contrarian position sizing and bubble protection.

---

### Task 1: Upgrade Prompt
**Files:**
- Modify: `tradingagents/prompts/zh.py`

- [ ] Add `game_theory_summary` placeholder to `portfolio_manager_prompt`.
- [ ] Instruct PM to adjust `target_weight_pct` based on `counter_consensus_signal` strength.

### Task 2: Refactor Portfolio Manager
**Files:**
- Modify: `tradingagents/agents/managers/portfolio_manager.py`

- [ ] Extract `game_theory_signals` from state.
- [ ] Use `summarize_game_theory_signals` (from `debate_utils.py`) to prepare text for the LLM.
- [ ] Pass the summary to the LLM call.

### Task 3: Verification
**Files:**
- Create: `tests/test_portfolio_gt_logic.py`

- [ ] Case 1: High Contrarian Buy Signal (Expected: Position Size Boost).
- [ ] Case 2: Retail FOMO Bubble Signal (Expected: Position Size Cap/Reduction).
