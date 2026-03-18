# Feature Spec: 010-portfolio-gt-integration

## User Story
As a risk-aware trader, I want the Portfolio Manager to incorporate Game Theory signals (contrarian indicators) into the final allocation logic so that my position sizing is smarter and avoids "Crowded Trades".

## Goals
- **Contrarian Position Sizing**: Boost allocation when GT signal is "High Conviction Contrarian" (e.g., Smart Money buying + Retail Panic).
- **Bubble Protection**: Drastically reduce allocation or suggest defensive hedging when GT signal indicates "Retail FOMO + Smart Money Distribution".
- **Signal Alignment**: Ensure the PM's final report explicitly mentions the game theory context.

## Core Logic
1. **Input**:
   - `game_theory_signals`: (JSON) `counter_consensus_signal`, `confidence`, `player_states`.
   - `allocation_details`: (Initial plan from Task 007).
2. **Analysis**:
   - Apply a "Game Theory Multiplier" to the Kelly Criterion result.
   - If `counter_consensus_signal` == "极强" and `direction` matches `trader_plan`, increase weight by 20-50%.
   - If `player_states["散户"]` == "极度贪婪" and `direction` is "BUY", cap the position at a lower level regardless of conviction.
3. **Output**:
   - Enhanced `portfolio_report`.
   - Updated `allocation_details` with GT-adjusted weight.

## Acceptance Criteria
- [ ] PM node correctly reads `game_theory_signals` from the state.
- [ ] Final report includes a "Game Theory Risk/Opportunity" section.
- [ ] Position size fluctuates based on contrarian strength in tests.
- [ ] Verified via integrated test case.
