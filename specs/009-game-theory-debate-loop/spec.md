# Feature Spec: 009-game-theory-debate-loop

## User Story
As a professional trader, I want the Smart Money and Retail agents to debate each other so that the system can simulate real-world chip distribution and psychological warfare, leading to more accurate "Contrarian" signals.

## Goals
- **Active Confrontation**: Move from independent reports to a claim-driven debate between "Institutional Logic" and "Retail Psychology".
- **Chip Modeling**: Simulate how smart money tries to wash out retail investors and how retail reacts to those moves.
- **Deeper Discrepancy Detection**: Use the debate to reveal where institutional intent and retail perception are most misaligned.

## Core Logic
1. **New State**: `GameTheoryDebateState` (mirroring `InvestDebateState`).
2. **Debate Workflow**:
   - `Smart Money Analyst` (Round 1: Strategy) -> `Retail Investor Analyst` (Round 1: Reaction)
   - (Optional Round 2 for rebuttal)
   - Final report handed to `Game Theory Manager`.
3. **Nodes**:
   - Refactor `SmartMoneyAnalyst` and `RetailInvestorAnalyst` to support debate history and claims.

## Acceptance Criteria
- [ ] `GameTheoryDebateState` integrated into `AgentState`.
- [ ] Smart Money and Retail agents exchange at least one round of views.
- [ ] `Game Theory Manager` synthesizes the results from the debate history rather than independent reports.
- [ ] Verified via E2E test.
