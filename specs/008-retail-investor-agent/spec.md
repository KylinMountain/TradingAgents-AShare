# Feature Spec: 008-retail-investor-agent

## User Story
As a professional trader, I want an agent to simulate the "Retail Herd Mindset" so that I can identify market sentiment extremes and profit from the contrarian gaps (Expectation Discrepancies) between smart money and retail crowd.

## Goals
- **Sentiment Extremes**: Identify if retail investors are in a state of "FOMO" (Fear Of Missing Out) or "Panic Selling".
- **Hot Pursuit Identification**: Detect if the current stock is a "Retail Hot Favorite" (high hype, low logic).
- **Sentiment Reversal Signals**: Detect when price action and retail sentiment are divergent.

## Core Logic
1. **Inputs**:
   - `get_zt_pool`: Daily limit-up pool to measure market-wide heat.
   - `get_hot_stocks_xq`: Retail search/follow trends.
   - `news_report`: Media narrative bias.
2. **Analysis**:
   - **Greed Index**: High retail heat + low institutional buy = Bubble trap.
   - **Fear Index**: High retail panic + institutional bottom fishing = Capitulation opportunity.
3. **Output**:
   - `retail_sentiment_report`: Psychological profile of the crowd.
   - **Retail Verdict**: Greed / Fear / Neutral.

## Acceptance Criteria
- [ ] `retail_investor_analyst.py` created and functional.
- [ ] Prompt defined in `zh.py` reflects the "Impulsive Retailer" persona.
- [ ] Integrated into the parallel analyst fan-out.
- [ ] Verified via unit/E2E test.
