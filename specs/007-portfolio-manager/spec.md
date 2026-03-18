# Feature Spec: 007-portfolio-manager

## User Story
As a trader, I want a specialized agent to manage my overall portfolio allocation so that individual stock recommendations are translated into concrete position sizes and hedging actions aligned with my risk profile.

## Goals
- **Position Sizing**: Calculate the exact amount of capital or shares to allocate for a recommended trade using Kelly Criterion or fixed-fractional sizing.
- **Sector Hedging**: Identify if the new trade increases sector risk concentration and suggest balancing actions.
- **Portfolio Rebalancing**: Generate specific "Buy/Sell/Hold" orders that transition the current portfolio state to the target state.
- **Final Verdict Integration**: Synthesize the results from the Risk Judge into a final, actionable portfolio summary.

## Core Logic
1. **Input**:
   - `trader_investment_plan`: The detailed trade setup.
   - `final_trade_decision`: The Risk Judge's verdict (pass/revise/reject).
   - `user_context`: Cash available, current positions, risk profile.
   - `market_context`: Sector/Macro backdrop.
2. **Analysis**:
   - Evaluate conviction (Confidence) vs. Portfolio Risk (Max Drawdown constraints).
   - Calculate sector exposure.
3. **Output**:
   - `portfolio_report`: Structured text report.
   - `allocation_details`: (JSON) Specific target weight and order size.

## Acceptance Criteria
- [ ] Portfolio Manager node exists in the LangGraph setup.
- [ ] Successfully reads `user_context` and calculates a position size.
- [ ] Includes a sector concentration check.
- [ ] Produces a final `portfolio_report` that summarizes the execution plan.
- [ ] Integrated as the final node before `END`.
