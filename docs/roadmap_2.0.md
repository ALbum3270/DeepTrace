# DeepTrace Roadmap 2.0: From MVP to Intelligent Agent

## 1. Current Status
- **Phase 7: Deep Analysis Loop (Completed)**
  - Core Loop: Fetch -> Extract -> Triage -> Build -> Planner (GainScore).
  - Capabilities: Deep content fetching, Event & Comment extraction, Timeline deduplication, Smart stop.
  - *See [docs/plan_v2.0_phase7.md](plan_v2.0_phase7.md) for detailed implementation plan.*

## 2. Architectural Evolution (The "Structure" Upgrade)

### 2.1 Explicit Parallelism (The "Fan-Out" Pattern)
**Goal**: Decouple event extraction from comment mining for better observability and modularity.
- **Change**: Split `extract_node` into `extract_events` and `extract_comments`.
- **Graph**:
  ```mermaid
  graph TD
      fetch --> extract_events
      fetch --> extract_comments
      extract_events --> build
      extract_comments --> triage --> build
  ```
- **Benefit**: Allows independent scaling and error handling for different extraction types.

### 2.2 Local Reflection Loops (The "Critic" Pattern)
**Goal**: Improve quality *before* the global loop decision.
- **Change**: Add "Critic" nodes for Timeline and Report.
- **Graph**:
  ```mermaid
  graph TD
      build --> timeline_critic
      timeline_critic -- "Refine" --> refine_timeline --> build
      timeline_critic -- "OK" --> planner
  ```
- **Benefit**: Self-correction of hallucinations or timeline inconsistencies without expensive re-fetching.

### 2.3 Supervisor & Router (The "Multi-Platform" Pattern)
**Goal**: Support platform-specific strategies (Phase 8 & beyond).
- **Change**: Introduce a `Supervisor` node to route requests.
- **Graph**:
  ```mermaid
  graph TD
      START --> supervisor
      supervisor -- "News" --> generic_graph
      supervisor -- "Social" --> social_graph
      supervisor -- "Deep Dive" --> deep_graph
  ```
- **Benefit**: Specialized subgraphs for different data sources (e.g., Weibo vs. News).

## 3. Next Steps (Phase 8: Platform Specifics)
- **Objective**: Implement platform-specific fetchers (e.g., Xiaohongshu, Weibo).
- **Alignment**: This naturally leads into the **Supervisor** pattern (2.3).
- **Plan**:
  1. Define `Platform` enum and detection logic.
  2. Implement `WeiboFetcher` / `XHSFetcher`.
  3. Refactor Graph to support routing (Supervisor Lite).
