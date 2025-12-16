# Implementation Plan: RAICT Lite (Phase 9 Refinement)

## 0. 目标 (Goal)

实现 "RAICT Lite" (Risk-Aware Information Collection & Triage - 精简工程版) 架构。
仅做一次全网广度搜集，随后的调查通过有限层数的 "广度-深度" 双池循环进行，确保资源集中在关键风险点 (High Beta, Low Alpha)。

## 1. 核心概念 (Core Concepts)

- **One-Shot Global Breadth (Layer 0)**: 唯一的一次利用 Supervisor 策略的全网扫描。
- **Layered Loop**: 循环结构，受 `MAX_LAYERS` 控制。
- **Two Pools**:
    - `breadth_pool`: 待扩展的搜索意图 (BreadthTask)。
    - `depth_pool`: 待验证的关键声明 (DepthTask)。
- **Task Prioritization (VoI)**: 基于 $VoI = \beta \times (1 - \alpha) / Cost$ 进行任务排序。

## 2. 数据模型变更 (Data Model Changes)

### 2.1 新增 Task 模型
**File**: `src/core/models/task.py` (New)
```python
class BreadthTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    layer: int
    query: str
    origin_claim_id: Optional[str] = None
    estimated_cost: float = 1.0
    # VoI Factors
    relevance: float = 0.0      # Topic match
    gap_coverage: float = 0.0   # Date/Topic gap
    novelty: float = 0.0        # Dissimilarity to prev queries
    voi_score: float = 0.0      # (Rel * Gap * Nov) / Cost
    metadata: Dict[str, Any] = {}

class DepthTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    layer: int
    claim_id: str
    estimated_cost: float = 2.0
    # VoI Factors
    beta_structural: float = 0.0 # Importance
    alpha_current: float = 0.0   # Current Credibility
    voi_score: float = 0.0       # Beta * (1 - Alpha) / Cost
```

### 2.2 更新 Claim 模型
**File**: `src/core/models/claim.py`
- 增加/映射字段：
    - `alpha` (mapping to `credibility_score` / 100.0)
    - `beta` (mapping to `importance` / 100.0)
    - `is_verified` (helper property)

### 2.3 更新 GraphState
**File**: `src/graph/state.py`
```python
class GraphState(TypedDict, total=False):
    # ... existing fields ...
    
    # RAICT Control
    current_layer: int
    breadth_pool: List[BreadthTask]
    depth_pool: List[DepthTask]
    
    # History & Tracking
    verified_claim_ids: Set[str]
    executed_queries: Set[str]      # For Novelty calc
    
    # Step Counters (reset per layer)
    current_layer_breadth_steps: int
    current_layer_depth_steps: int
```

## 3. 核心组件 (Core Components)

### 3.1 Controller Router (The Brain)
**File**: `src/graph/nodes/controller.py` (New)
**Function**: `controller_node` / `route_controller`
- Logic:
    1. Check `MAX_LAYERS` -> Finish.
    2. Check `breadth_pool` (current layer) & Step Limit -> `breadth_node`.
    3. Check `depth_pool` (current layer) & Step Limit -> `depth_node`.
    4. Check next layer availability -> Increment Layer, Reset Steps -> Recurse.
    5. Else -> Finish.

### 3.2 Breadth Node (Refactored)
**File**: `src/graph/nodes/breadth_node.py`
- **Layer 0**:
    - If pool empty, create initial task from user query.
    - Run `Supervisor` -> `Fetch` -> `Extract`.
    - Populate `depth_pool` (High Beta claims).
    - Populate `breadth_pool` (L1) if any expansion needed.
- **Layer > 0**:
    - Pop tasks from `breadth_pool` (L=current).
    - Run targeted fetch.
    - Extract -> Update Pools.

### 3.3 Depth Node (Refactored from Verification)
**File**: `src/graph/nodes/depth_node.py`
- Pop Top-K VoI tasks from `depth_pool` (L=current).
- For each task (Claim):
    - Generate specific verification queries (e.g., `site:official.com ...`).
    - Fetch & Extract.
    - Update Claim `alpha` & `status`.
    - If new info found -> Create new L+1 tasks.

### 3.4 Triage Node (Candidate Generation & Scoring)
**File**: `src/graph/nodes/triage_node.py` (New)
**Logic**:
1. **Candidate Generation**:
   - **Depth**: Scan all Claims not in `verified_claim_ids`.
   - **Breadth**: 
     - Detect Timeline Gaps (Date ranges with 0 events).
     - Identify High-Beta Claims needing context (e.g., "Reaction to X").
     - Identify User Query sub-aspects not covered.
2. **Scoring (VoI)**:
   - **Breadth**: `VoI = (Relevance * GapCoverage * Novelty) / Cost`.
     - *Novelty*: 1 - max(similarity(q, executed_queries)).
   - **Depth**: `VoI = Beta * (1 - Alpha) / Cost`.
3. **Filtering & Routing**:
   - Only add tasks with `VoI > Threshold` to pools.
   - Sort pools by `VoI` descending.

## 4. 配置 (Configuration)

**File**: `src/config/settings.py`
```python
# RAICT Lite Settings
MAX_LAYERS = 2
MAX_BREADTH_STEPS_PER_LAYER = 3
MAX_DEPTH_STEPS_PER_LAYER = 3
VOI_WEIGHT_BETA = 1.0
BREADTH_VOI_THRESHOLD = 0.5
DEPTH_VOI_THRESHOLD = 0.5
```

## 5. 执行计划 (Execution Steps)

- [ ] **Step 1**: Define `BreadthTask` and `DepthTask` models in `src/core/models/task.py`.
- [ ] **Step 2**: Update `GraphState` in `src/graph/state.py` with new pools and counters.
- [ ] **Step 3**: Implement `controller.py` with the routing logic described.
- [ ] **Step 4**: Refactor `extract_node.py` to generate *Tasks* instead of just raw data, or have a separate `task_generator` node. (Decision: Let's keep extraction pure, add a `triage_node` to convert Claims/Info to Tasks).
    - *Amendment*: Add `triage_node` after Extraction to calculate VoI and populate pools.
- [ ] **Step 5**: Refactor `workflow.py` to use `controller` -> `breadth` / `depth` -> `triage` -> `controller` loop.
- [ ] **Step 6**: Update `report_writer.py` to use the Verified/Unverified distinction strictly.
- [ ] **Step 7**: Verify with `DeepSeek` query.

## 6. 测试 (Tests)

- `test_raict_controller.py`: Unit test for routing logic (states -> expected next node).
- `test_voi_sorting.py`: Unit test for task prioritization.
- Integration run.
