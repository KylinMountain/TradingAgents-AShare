# Trading Agents Evolution: "The Alpha Nexus" Design Document

## 1. Vision & Strategy

We are transitioning the system from a "linear report generator" into a **highly autonomous, multidimensional intelligence nexus**. The selected evolution directions (1, 4, 6, 8, 9, 10) form a cohesive strategy:

1.  **Deep Game Theory (1)**: The core engine moves from summarizing to simulating.
2.  **Autonomous Information Retrieval (4)**: The ReAct loop gives agents agency to dig deeper.
3.  **Cross-Entity Ecosystem (6)**: Analysis expands from single-stock to a localized supply chain/competitor graph.
4.  **Temporal & Visual Intelligence (8, 9)**: Incorporating historical pattern matching and multimodal chart analysis.
5.  **Micro-structure Surveillance (10)**: Deep-diving into LHB and institutional flow to detect traps.

## 2. Proposed Architecture: The "Alpha Nexus"

To support these, we must upgrade the LangGraph architecture. The linear `Analyst -> Manager -> Judge` pipeline will be enhanced with inner loops and specialized nodes.

### 2.1 The Autonomous Analyst Cluster (Addressing #4, #6, #8, #9, #10)

Instead of running one pass, analysts now have inner `ReAct` loops.

*   **Ecosystem Analyst (Evolution of #6)**:
    *   **Input**: Target Ticker.
    *   **Action**: Retrieves immediate Upstream, Downstream, and Competitors.
    *   **Loop**: Analyzes news/fundamentals for the *entire cluster* to validate the target's narrative.
*   **Whale Detector Analyst (Evolution of #10 & #4)**:
    *   **Input**: Target Ticker.
    *   **Action**: Analyzes LHB (龙虎榜), Block Trades.
    *   **Loop**: If a suspicious pattern is found, it *autonomously triggers a sub-search* on the specific trading seats involved (e.g., "Has this seat dumped on day 2 recently?").
*   **Time-Machine Analyst (Evolution of #8)**:
    *   **Action**: Queries a Vector DB of historical market states matching current conditions.
*   **Visual Chart Analyst (Evolution of #9)**:
    *   **Action**: Takes raw image inputs of K-lines and order book heatmaps for structural analysis.

### 2.2 The Simulation Engine (Addressing #1)

The `Game Theory Manager` is upgraded to the `Market Simulator`.

*   **Inputs**: Signals from all analysts (including Ecosystem, Whale, and Time-Machine).
*   **Process**: It defines the "Board" (retail vs. institution vs. quant). It projects 2-3 potential scenarios based on the conflicting forces discovered by the analysts.
*   **Output**: A structured payoff matrix and a dominant strategy path.

### 3. Implementation Phasing

Because doing all of this at once is risky, we will phase it:

*   **Phase 1: The ReAct Upgrade (#4 & #10)**: Upgrade `SmartMoneyAnalyst` to a ReAct agent. Allow it to look at LHB, find a seat, and query history for that seat. This proves the autonomous loop works.
*   **Phase 2: The Ecosystem Expansion (#6)**: Create the `EcosystemAnalyst`. Connect an API to fetch competitors/suppliers and run parallel analysis.
*   **Phase 3: The Simulation Engine (#1)**: Refactor the `GameTheoryManager` to consume the richer data and output structured scenarios.
*   **Phase 4: Multimodal & Temporal (#8 & #9)**: Introduce the Vector DB for history matching and multimodal LLM calls for chart reading.
