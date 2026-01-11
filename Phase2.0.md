下面是**最终可直接贴进 repo 的 Phase 2 v1.2.2 完整文本**（= 你现有 v1.2.1 + 我刚才建议的“几行就能锁死语义”的补丁全部就地合并）。
建议文件名：`docs/phases/phase2_v1.2.2.md`

---

# DeepTrace V2 — Phase 2 v1.2.2

**（可回滚、可复盘、可证伪的迭代研究工程化）**

> v1.2.2 变更摘要（相对 v1.2.1 的“低成本硬化”）
>
> 1. **signals null 必须解释**：任何 `signals.* == null` → `reason_codes` 必须包含 `SIGNAL_UNAVAILABLE_*`（CI 可测）
> 2. **dup_rate 口径冻结**：Phase 2 统一冻结为 URL 口径 `deduped_urls/attempted_urls`，并写死 `dup_rate_method_version="url_v1"`
> 3. **conflict_blocks 字段落点写死**：以 `structured_report.conflict_blocks[]` 为合同字段；sidecar 仅镜像；Gate2 只看 sidecar 镜像字段，不读 report.md
> 4. **Router debug 输入可回看**：增加 `router_inputs_snapshot_ref`（可选调试镜像）与 digest 组合
> 5. **replay_pack 默认自包含语义写死**：`replay_r1_offline.py` 默认要求 replay_pack 自包含全部输入；external_ref 默认 CI 禁止
> 6. **ablation 记录模型/SDK**：`model_provider/model_id/client_sdk_version` 写死进 evaluation_report
> 7. **脚本退出码语义写死**：统一 exit codes，CI 对接无歧义

---

## 0. 本阶段总目标（写死）

1. **覆盖↑、重复↓、成本可控**：breadth×depth + Router + 去重 + StopDecision（启发式+否决门）
2. **可演进事实库**：doc_key/doc_version_id + event_id/node_id + CDC diff（可审计变更集）
3. **可回放（R1）**：replay_pack（A 路径：清洗后 chunks 快照 + manifest）+ 断网重放 Gate/Stop/CDC
4. **可证伪实验**：policy_registry + ablation runner + evaluation_report（baseline vs variant）
5. **最小评估与观测闭环**：Ragas（默认冻结 2 指标）+ TruLens tracing（可归档）

---

## 1. Feature Flags（必须全量支持回滚）

> 所有 Phase 2 新能力必须能一键回滚到 Phase 0/1 稳定链路。

* `FF_ROUTER`：启用 RouterNode（breadth/depth/mixed/fallback）
* `FF_BREADTH_DEPTH`：启用 breadth×depth 编排（round-based loop）
* `FF_DEDUP_TRACKER`：启用 `visited_urls + seen_queries`（规范化去重）
* `FF_STOP_CONTROLLER`：启用 StopControllerNode（signals+veto+reason_codes）
* `FF_DOC_VERSIONING`：启用 doc_key/doc_version_id（文档族与内容版本）
* `FF_EVENT_ID_V1`：启用跨 run 稳定 event_id（versioned）
* `FF_CDC_MERGE`：启用 MergeCDCNode（CDC diff）
* `FF_REPLAY_PACK_A`：启用 replay_pack A 路径（chunks 快照）
* `FF_POLICY_REGISTRY`：启用 policy_registry（system/curated/experimental）
* `FF_ABLATION_RUNNER`：启用 ablation runner（baseline vs variant）
* `FF_EVAL_RAGAS`：启用 Ragas 离线评估（冻结 2 指标）
* `FF_TRACE_TRULENS`：启用 TruLens tracing（归档 spans）

---

## 2. Phase 2 拆解为 5 个小计划（2A–2E）

* **2A：Orchestration 最小闭环**（breadth×depth + 并发抓取 + Router + 去重 + StopDecision 落盘）
* **2B：Version / ID / CDC**（doc_version 家族 + event_id 稳定化 + CDC diff 可审计）
* **2C：Replay R1（断网可回放）**（replay_pack A + 离线重跑 Gate/Stop/CDC）
* **2D：Policy & Ablation（实验门禁）**（policy_registry + ablation runner + evaluation_report + Stop-RAG 对照候选）
* **2E：Eval & Tracing 最小接入**（Ragas 冻结 2 指标 + TruLens tracing 归档）

> 你之前的“Phase 2.5（实验门禁）”在 v1.2.2 中合并进 **2D/2E**，但仍保持：**experimental 默认不上线**。

---

## 3. 统一脚本退出码语义（写死）

> 所有 `scripts/*.py` 验收脚本必须遵守同一退出码语义，CI/PR 门禁不做二次解释。

* `0`：PASS
* `2`：Schema invalid / Contract missing required fields
* `3`：Determinism mismatch（同输入同版本产物不一致）
* `4`：Missing required artifacts（缺文件/缺目录/缺关键产物）
* `5`：Gate hard fail（Gate2 hard 或被明确指定的 hard 条件）
* `10`：Unexpected runtime error（异常/崩溃）

---

# 2A. Orchestration 最小闭环（覆盖↑、重复↓、成本可控）

## 2A.1 目标（写死）

交付一个“能跑、能停、能复盘”的研究编排骨架：

* breadth×depth round loop（可配置）
* 并发池、限速、失败降级（FetchBatch）
* `visited_urls + seen_queries`（规范化 query 去重）
* Router（条件/分支/fallback）
* StopDecision（启发式 + 否决门 + reason_codes 枚举）
* **RoundRecord 从 2A 起一次写全字段**（允许 null/0，但字段必须存在）

### 2A.1.1 产物真源规则（写死）

* **RoundRecord 是唯一真源（source of truth）**：回放/对照/审计一律以 `rounds/round_{k}.json` 为准
* `data/runs/{run_id}/decisions/router_{k}.json` 与 `stop_{k}.json` **仅为调试镜像（可选）**，且必须能由 RoundRecord 确定性重建；任何不一致以 RoundRecord 为准

---

## 2A.2 Prior Art（就地映射，不只“末尾堆链接”）

### 2A.2.1 Iterative Retrieval Skeleton（breadth×depth / visited_urls）

**GPT-Researcher（工程参照）**
Borrow Point：

* breadth×depth 的迭代研究骨架
* 并发抓取、失败降级、visited_urls 控制点
  Used by：FetchBatchNode、RoundOrchestratorNode、DedupTrackerNode
  Links：
* [https://github.com/assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)
* [https://docs.gptr.dev/docs/gpt-researcher/getting-started](https://docs.gptr.dev/docs/gpt-researcher/getting-started)

### 2A.2.2 Router / Branching

**Haystack ConditionalRouter**
Borrow Point：条件命中 + fallback 语义、路由可解释性
Used by：RouterDecision 合同（route/fallback_route/rationale_codes）
Link：[https://docs.haystack.deepset.ai/docs/conditionalrouter](https://docs.haystack.deepset.ai/docs/conditionalrouter)

**LlamaIndex RouterQueryEngine**
Borrow Point：多引擎/多策略选择范式、选择依据结构化
Used by：RouterNode（多策略池选择），后续 2D policy_registry 形态
Link：[https://developers.llamaindex.ai/python/examples/query_engine/routerqueryengine/](https://developers.llamaindex.ai/python/examples/query_engine/routerqueryengine/)

**LangChain RunnableBranch**
Borrow Point：分支执行抽象（branch runnable），用于组织分支子图
Non-goal：不强行切换到 LC Runnable 栈；只借鉴抽象
Used by：LangGraph 子图分支组织（breadth/depth/fallback）
Link：[https://reference.langchain.com/javascript/classes/_langchain_core.runnables.RunnableBranch.html](https://reference.langchain.com/javascript/classes/_langchain_core.runnables.RunnableBranch.html)

---

## 2A.3 数据合同（Schemas）（写死）

> schema 必须先落地（Pydantic + JSON Schema），并在 CI 校验。

### 2A.3.1 RouterDecision（新增，最小 schema）

```json
{
  "router_version": "v1",
  "route": "breadth|depth|mixed|fallback",
  "fallback_route": "breadth|depth|mixed|null",
  "rationale_codes": ["..."],
  "budget_hint": { "max_rounds": 0, "max_docs": 0, "max_calls": 0 },
  "inputs_digest": "sha256...",
  "router_inputs_snapshot_ref": "data/runs/{run_id}/router_inputs/router_{k}.json|null"
}
```

> `router_inputs_snapshot_ref` 是**可选调试镜像**：允许存在但**不作为真源**；若存在，必须与 `inputs_digest` 对得上。

### 2A.3.2 DedupTracker（最小字段）

* `visited_urls[]`（canonical url）
* `seen_queries[]`（normalized query）
* `query_fingerprint` = hash(normalized_query)（便于解释重复）
* `url_canonicalization_version="url_v1"`（写死）

### 2A.3.3 StopDecision（Phase 2 稳定版，写死）

```json
{
  "decision": "continue|stop",
  "signals": {
    "new_events": null,
    "new_nodes": null,
    "dup_rate": 0.0,
    "dup_rate_method_version": "url_v1",
    "new_sources": null,
    "recency_best_days": null,
    "coverage_score": null,
    "tokens_per_new_event": null
  },
  "vetoes": ["UNRESOLVED_CONFLICTS", "RECENCY_NOT_MET", "COVERAGE_GAP", "BUDGET_GUARD"],
  "reason_codes": ["..."],
  "enabled_policies_snapshot": { "router": "v1", "stop": "heuristic_v1", "flags": ["..."] }
}
```

**硬规则（可测）**：

1. 若 signals 触发 stop 但存在 veto：

* `decision=continue` 且 `reason_codes` **必须包含** `BLOCKED_BY_VETO_*`

2. **signals 为 null 的硬合同（v1.2.2 写死）**：

* 任何 `signals.<field> == null`，`reason_codes` **必须包含** `SIGNAL_UNAVAILABLE_<FIELD>`
  否则：schema-valid 但 **contract invalid（CI fail）**

#### 2A.3.3.1 Stop signals 口径表（允许 null，但必须可解释）

| signal                 | Phase 2 口径（强定义）                                         | 暂不可用时（允许）                                                      | 备注                                 |
| ---------------------- | ------------------------------------------------------- | -------------------------------------------------------------- | ---------------------------------- |
| `new_events`           | 2B 启用 CDC 后：`MergeResult.added_events.length`           | `null` + `SIGNAL_UNAVAILABLE_NEW_EVENTS`                       | 2A 阶段不要自造替代口径                      |
| `new_nodes`            | 本轮新增 node 数（新增 evidence 节点）                             | `null` + `SIGNAL_UNAVAILABLE_NEW_NODES`                        |                                    |
| `dup_rate`             | **冻结口径（v1.2.2）：**`deduped_urls/attempted_urls`          | `null` + `SIGNAL_UNAVAILABLE_DUP_RATE`                         | `dup_rate_method_version="url_v1"` |
| `new_sources`          | 2B+：本轮新增 `publisher_id` 数（去重后）                          | 2A 可用 domain 粗算，但必须写 `sources_count_method_version`；否则置 `null` | 强烈建议 2B 起统一成 publisher_id          |
| `recency_best_days`    | 本轮可用文档中最“新”的发布日期距今天数                                    | `null` + `SIGNAL_UNAVAILABLE_RECENCY_BEST_DAYS`                | 需记录 `recency_parse_version`        |
| `coverage_score`       | 占位（Phase 2 可为 null）                                     | `null`（可不加 unavailable）                                        |                                    |
| `tokens_per_new_event` | `round_tokens / max(new_events,1)`（当 new_events 非 null） | `null` + `SIGNAL_UNAVAILABLE_TOKENS_PER_NEW_EVENT`             |                                    |

---

### 2A.3.4 RoundRecord（2A 起字段一次写全）

> 允许暂时填 0/null，但字段必须存在，否则历史 run 不可比。

```json
{
  "run_id": "...",
  "round_id": 0,
  "query_ids": ["..."],
  "doc_version_ids": ["..."],
  "router_decision": { },
  "stop_decision": { },
  "merge_result": null,
  "cost": { "tokens": 0, "calls": 0, "latency_ms": 0 },
  "signals_summary": {
    "new_urls": 0,
    "deduped_urls": 0,
    "new_queries": 0,
    "deduped_queries": 0,
    "fetch_errors": 0
  },
  "enabled_policies_snapshot": { }
}
```

---

## 2A.4 LangGraph 节点流（增量，不破坏 Phase0/1）

新增/增强节点（建议顺序）：

1. `RoundOrchestratorNode`（breadth×depth loop 驱动）
2. `FetchBatchNode`（并发/限速/失败降级）
3. `DedupTrackerNode`（visited_urls/seen_queries）
4. `RouterNode`（选择 breadth/depth/mixed/fallback 子图）
5. `StopControllerNode`（signals+veto+reason_codes + 防抖）
6. `ArchiveRoundNode`（RoundRecord 落盘，必须）

---

## 2A.5 Deliverables（产物）

* `runs/{run_id}/rounds/round_{k}.json`（RoundRecord，**唯一真源**）
* `data/runs/{run_id}/dedup/dedup_state.json`
* `data/runs/{run_id}/decisions/router_{k}.json`（可选镜像）
* `data/runs/{run_id}/decisions/stop_{k}.json`（可选镜像）
* （可选）`data/runs/{run_id}/router_inputs/router_{k}.json`（可选镜像）

---

## 2A.6 PR 拆解（附参照链接）

* **PR2A-1**：FetchBatchNode（并发池/限速/失败降级）+ DedupTracker 基础落盘
  Ref：GPT-Researcher

  * [https://github.com/assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)
  * [https://docs.gptr.dev/docs/gpt-researcher/getting-started](https://docs.gptr.dev/docs/gpt-researcher/getting-started)

* **PR2A-2**：RouterNode + RouterDecision schema + 分支子图（breadth/depth/fallback）
  Ref：

  * [https://docs.haystack.deepset.ai/docs/conditionalrouter](https://docs.haystack.deepset.ai/docs/conditionalrouter)
  * [https://developers.llamaindex.ai/python/examples/query_engine/routerqueryengine/](https://developers.llamaindex.ai/python/examples/query_engine/routerqueryengine/)
  * [https://reference.langchain.com/javascript/classes/_langchain_core.runnables.RunnableBranch.html](https://reference.langchain.com/javascript/classes/_langchain_core.runnables.RunnableBranch.html)

* **PR2A-3**：StopControllerNode（启发式+防抖+veto 优先）+ signals 口径表落地（允许 null 但必须解释）

---

## 2A.7 验收（可执行）

`scripts/run_orchestration_smoke.py`：

* 运行 1 个 topic（或 fixture）
* 必须产出：RoundRecord + RouterDecision + StopDecision
* StopDecision 若被 veto 阻止停止：必须包含 `BLOCKED_BY_VETO_*`
* RoundRecord 必须 schema-valid（字段齐全）
* 退出码遵守 §3

---

# 2B. Version / ID / CDC（可演进事实库的“变更集”）

## 2B.1 目标（写死）

* doc_key/doc_version_id 正式启用（文档族 + 内容版本）
* event_id 跨 run 稳定（versioned）
* MergeCDCNode 输出 CDC diff（added/updated/deduped/conflict_candidates + digests）
* 为后续冲突呈现/verified 门槛提供可审计抓手（但 Phase 2 不强上最终 verified 体系）

---

## 2B.2 合同（写死）

### 2B.2.1 doc_key / doc_version_id 语义（必须写死）

* `doc_key = final_url_normalized`（规范化 URL 字符串）：表示“文档族”
* `doc_version_id = hash(hash(doc_key) + content_hash)`：表示“该族的一个内容版本”
* `DocVersionResolver` 必须维护：`doc_key -> latest_doc_version_id`（按 retrieved_at 或 published_at 规则）

硬要求：

* `url_canonicalization_version="url_v1"` 必须写进 DocumentSnapshot（必填，与 normalizer/splitter 同级）
* canonicalization 版本变更 → 必须触发回放/回归（否则 doc_key family 漂）

### 2B.2.2 event_id / node_id（versioned）

* `event_id_version = v1`
* `event_id`：语义稳定（不含 span/offset），由规范化后（日期/实体/标题/断言）hash 得到
* `node_id`：证据版本（包含 doc_version_id + sentence_ids/span digest）

---

## 2B.3 CDC diff（MergeResult）最小 schema（写死）

```json
{
  "added_events": [{ "event_id": "...", "node_ids": ["..."] }],
  "updated_events": [{
    "event_id": "...",
    "fields_changed": ["title","date","numbers","status","..."],
    "before_digest": "sha256...",
    "after_digest": "sha256...",
    "evidence_basis": "NEW_DOC_VERSION|NEW_SOURCE|HIGHER_TIER_EVIDENCE|CONFLICT_FIX"
  }],
  "deduped_events": [{ "event_id": "...", "dedupe_key": "...", "rationale": "..." }],
  "conflict_candidates": [{
    "conflict_group_id": "...",
    "type": "NUMERIC_DISAGREE|DATE_DISAGREE|STATUS_DISAGREE|...",
    "member_event_ids": ["..."],
    "rationale": "..."
  }]
}
```

---

## 2B.4 节点流（增量）

* `DocVersionResolverNode`（doc_key family / latest）
* `ExtractEventsNode v2`（**主路径硬规则**：返回 `doc_version_id + chunk_id + sentence_ids/span`；quote 由程序截取；LLM 不得改写 quote）
* `MergeCDCNode`（输出 MergeResult/CDC）
* `ArchiveRoundNode`（RoundRecord.merge_result 写入）

---

## 2B.5 PR 拆解

* **PR2B-1**：doc_key/doc_version_id 正式启用 + DocVersionResolverNode
* **PR2B-2**：event_id v1（稳定化 + 版本化 canonicalization）
* **PR2B-3**：MergeCDCNode（CDC diff + digests + evidence_basis）

---

## 2B.6 验收（可执行）

`scripts/check_cdc_integrity.py`：

* 校验 CDC schema
* 校验 `before_digest/after_digest` 非空
* 校验 `evidence_basis` 枚举合法
* 同输入重跑：event_id 稳定率记录（先记录不硬挡，后续再硬化）
* 退出码遵守 §3

---

# 2C. Replay R1（断网可回放、可复盘）

## 2C.1 目标（写死）

* replay_pack 走 **A 路径**：存清洗后 chunks 快照 + manifest
* 断网可重放至少：Gate1 + Gate2 + StopDecision + MergeCDC（不重放抓取也能对比）
* 为 2D ablation runner 提供“同证据、不同策略”的可复跑基座

---

## 2C.2 replay_pack A 路径合同（写死）

目录（写死）：

* `replay_pack/{run_id}/manifest.json`
* `replay_pack/{run_id}/versions.json`
* `replay_pack/{run_id}/chunks/{doc_version_id}.jsonl.zst`

manifest 最小必须包含：

* `doc_version_id -> file_path`
* `chunk_id -> line_no/offset`
* `normalization_version / sentence_splitter_version / extractor_version / url_canonicalization_version`

### 2C.2.1 versions.json（统一版本快照入口，写死）

`replay_pack/{run_id}/versions.json`（回放与 ablation **只读此处**获取版本快照）至少包含：

* extractor/cleaner/normalizer/sentence_splitter/chunk_splitter
* url_canonicalization_version
* router_version/stop_version/event_id_version/merge_cdc_version
* gate1_version/gate2_version
* （如启用 2E）ragas_version/trulens_version + judge_config_digest

---

## 2C.3 R1 最小回放集合（写死）

replay_pack/R1 必须包含（或在 replay_pack 内自包含可离线寻址）：

* `facts_index_v2.json`
* `structured_report.json` + `report_citations.json`
* `gate1_report.json` + `gate2_report.json`
* `RoundRecord[]` + `StopDecision` + `MetricsSummary`
* `DocumentSnapshot`（至少 doc_version_id + versions + chunks/sentences index）
* `manifest.json` + `versions.json`

### 2C.3.1 replay_pack “默认自包含”语义（v1.2.2 写死）

* `scripts/replay_r1_offline.py` **默认要求 replay_pack 自包含全部输入**
* 若使用 `external_ref`（例如引用 runs/{run_id} 的外部文件），必须显式开启 `--allow-external-ref`，且 **CI 默认禁止**

---

## 2C.4 PR 拆解

* **PR2C-1**：replay_pack A 落盘（chunks 快照 + manifest + versions.json）
* **PR2C-2**：离线 replay 脚本（R1）：重跑 Gate1/Gate2/Stop/MergeCDC（校验 versions.json + 自包含语义）

---

## 2C.5 验收（可执行）

`scripts/replay_r1_offline.py --replay_pack ...`：

* 断网环境下可运行
* 产出 replay_report（一致性/差异点）
* Gate 报告可复现（同输入同版本产物一致）
* 退出码遵守 §3

### 2C.5.1 存储与保留策略（占位，避免量爆）

> Phase 2C 不要求立即实现自动清理，但必须写明默认策略。

默认建议（可配置但字段名写死）：

* `retention_policy`: `{ "keep_days": 14, "keep_runs": 200, "keep_replay_packs": 50 }`
* 超限降级（允许）：

  * 保留 `manifest.json + versions.json + gates + round_records + metrics`
  * replay chunks 仅保留 **key_claim 引用到的 doc_version_id**（策略版本化并落盘）

---

# 2D. Policy & Ablation（实验门禁：把“未验证策略”变成可证伪）

## 2D.1 目标（写死）

* policy_registry：`system / curated / experimental`
* ablation runner：baseline vs variant（replay_pack 驱动）
* evaluation_report：指标 + 成本 + 失败样例 + 边界说明
* Stop-RAG 仅作为 experimental 对照候选（通过门禁再进 curated）

---

## 2D.2 policy_registry 合同（写死）

* policy_id：如 `system/router_v1`, `experimental/stoprag_v0`
* snapshot：router/stop/merge/extract 的版本号 + feature flags
* 所有 experimental 策略必须可回滚，不允许覆盖 system 默认

---

## 2D.3 ablation protocol（最小晋级门槛，写死）

对固定评估集（replay_pack 冻结证据）：

* `gate2_hard_fail_count` 不上升
* `key_claim_locatable_rate` 不下降（或下降 ≤ X%）
* `cost_per_added_event` 不显著恶化（允许 +Y% 若 coverage 明显提升）
* 必须输出 `failure_examples[]`（至少 3 个）

### 2D.3.1 可重复性约束（写死）

* 默认固定 `seed`
* 默认 `temperature=0`（或等价确定性采样）；若不为 0，必须记录并解释原因
* evaluation_report 必须记录：

  * `model_provider` / `model_id` / `client_sdk_version`
  * `prompt_version`（或 digest）
  * `seed` / `temperature` / `sample_count`
  * `input_replay_pack_id` + `versions.json` digest

---

## 2D.4 Stop-RAG（Experimental Control Candidate）

Borrow Point：作为“停机策略实验对照组”，用于 ablation baseline vs variant
Non-goal：Phase 2 不训练、不默认上线；只允许 experimental 下运行
Used by：ablation runner 对照策略池 `experimental/stoprag`
Links：

* [https://arxiv.org/abs/2510.14337](https://arxiv.org/abs/2510.14337)
* [https://github.com/chosolbee/Stop-RAG](https://github.com/chosolbee/Stop-RAG)

---

## 2D.5 PR 拆解

* **PR2D-1**：policy_registry + enabled_policies_snapshot 贯通（RoundRecord/StopDecision）
* **PR2D-2**：ablation runner（baseline system vs variant）+ 可重复性约束落盘
* **PR2D-3**：evaluation_report 规范（json schema + failure_examples）

---

## 2D.6 验收（可执行）

`scripts/run_ablation.py --baseline system --variant experimental/xxx --replay_pack ...`：

* 必须产出：`evaluation_report.json`
* 必须包含：指标、成本、失败样例、结论（晋级/不晋级）
* 必须包含：model_provider/model_id/client_sdk_version + seed/temperature/prompt_version/sample_count
* 退出码遵守 §3

---

# 2E. Eval & Tracing（最小接入：先 1+1 固定）

## 2E.1 目标（写死）

* 离线评估：**Ragas**（Phase 2E 默认）
* tracing/观测：**TruLens**（Phase 2E 默认）
* 评估/观测产物必须归档进 run 包，能被回放/对比

---

## 2E.2 Ragas（默认冻结 2 指标，写死）

> Phase 2E 默认只跑 2 个指标：`faithfulness` + `answer_relevancy`
> 其余仅作为 `optional_metrics`，不得进入默认 CI，避免不稳定拖慢合入。

Borrow Point：指标定义与口径（离线 eval artifact）
Used by：`scripts/run_eval_ragas.py` + `eval_run.json`
Links：

* [https://github.com/vibrantlabsai/ragas](https://github.com/vibrantlabsai/ragas)
* [https://docs.ragas.io/en/latest/](https://docs.ragas.io/en/latest/)

### 2E.2.1 judge/口径记录项（写死，确保可复现）

`eval_run.json`（或 `versions.json`）必须记录：

* `judge_model_id`
* `judge_temperature`（默认 0）
* `judge_prompt_version`（或 digest）
* `context_source = "replay_pack_chunks"`（写死：contexts 来自回放证据，不在线检索）
* `ragas_metrics_enabled = ["faithfulness","answer_relevancy"]`

---

## 2E.3 TruLens tracing（默认）

Borrow Point：tracing span 可归档、可定位到 Router/Stop/Merge/Finalizer
Non-goal：Phase 2E 不强制复杂 feedback functions 全上
Used by：`scripts/run_trace_trulens.py` + trace artifacts
Links：

* [https://github.com/truera/trulens](https://github.com/truera/trulens)
* [https://www.trulens.org/](https://www.trulens.org/)

---

## 2E.4 PR 拆解

* **PR2E-1**：EvalHarness（统一入口）+ Ragas 2 指标默认跑通 + judge 口径落盘
* **PR2E-2**：TruLens tracing 接入 + trace 归档（run 级）

---

## 2E.5 验收（可执行）

* `scripts/run_eval_ragas.py --replay_pack ...` → `runs/{run_id}/eval/eval_run.json`
* `scripts/run_trace_trulens.py --run_id ...` → `runs/{run_id}/traces/traces.jsonl` + manifest
  退出码遵守 §3

---

# 4. Gate 纪律（延续 Phase 0 核心原则）

## 4.1 Gate2 永不解析 report.md（写死）

* RenderMarkdownNode 可以输出 Conflict Block marker（给人看）
* **ExportSidecarNode 必须同步导出结构字段**：

  * `conflict_blocks[]: [{conflict_group_id, item_ids[]}]` 或 `has_conflict_block=true`
* **Gate2 只检查 sidecar 的 conflict_blocks**，不解析 report.md

## 4.2 conflict_blocks 的 schema 落点与导出责任（v1.2.2 写死）

* **Schema Source（合同落点）：** `structured_report.conflict_blocks[]` 为强字段
* ExportSidecarNode 将其镜像导出到 sidecar（report_citations）
* Gate2 只检查 sidecar 镜像字段是否存在/匹配，但不读 report.md

---

# 5. reason_codes（枚举写死）

至少包含：

* `STOP_MAX_ROUNDS`
* `STOP_BUDGET_GUARD`
* `STOP_LOW_DELTA_CONSECUTIVE`（要求连续 K 轮）
* `STOP_HIGH_DUP_RATE_CONSECUTIVE`（要求连续 K 轮）
* `STOP_COVERAGE_REACHED`（占位）
* `STOP_RECENCY_MET`（占位）
* `CONTINUE_MIN_ROUNDS_NOT_MET`
* `BLOCKED_BY_VETO_UNRESOLVED_CONFLICTS`
* `BLOCKED_BY_VETO_RECENCY_NOT_MET`
* `BLOCKED_BY_VETO_COVERAGE_GAP`
* `SIGNAL_UNAVAILABLE_NEW_EVENTS`
* `SIGNAL_UNAVAILABLE_NEW_NODES`
* `SIGNAL_UNAVAILABLE_DUP_RATE`
* `SIGNAL_UNAVAILABLE_RECENCY_BEST_DAYS`
* `SIGNAL_UNAVAILABLE_TOKENS_PER_NEW_EVENT`
* （可选）`SIGNAL_UNAVAILABLE_NEW_SOURCES`

---

# 6. Repo 目录与产物约定（建议写死）

* `schemas/`：所有 JSON Schema（RouterDecision/StopDecision/RoundRecord/MergeResult/eval_run…）
* `scripts/`：可执行验收脚本（smoke/cdc/replay/ablation/eval/trace）
* `runs/{run_id}/`：

  * `rounds/round_{k}.json`（唯一真源）
  * `decisions/router_{k}.json`（可选镜像）
  * `decisions/stop_{k}.json`（可选镜像）
  * `router_inputs/router_{k}.json`（可选镜像）
  * `cdc/merge_{k}.json`
  * `gates/gate1_report.json`
  * `gates/gate2_report.json`
  * `eval/eval_run.json`
  * `traces/`
* `replay_pack/{run_id}/`：

  * `manifest.json`
  * `versions.json`
  * `chunks/{doc_version_id}.jsonl.zst`

---

# Appendix A. Canonical Links（权威入口汇总）

> 注意：每个链接在正文对应模块（2A/2D/2E）均已标注 Borrow Point + Used by。
> 本节仅做权威入口汇总，避免重复维护。

```text
[Iterative Retrieval Skeleton / breadth×depth / visited_urls]
- GPT-Researcher
  https://github.com/assafelovic/gpt-researcher
  https://docs.gptr.dev/docs/gpt-researcher/getting-started

[Router / Branching References]
- Haystack ConditionalRouter
  https://docs.haystack.deepset.ai/docs/conditionalrouter
- LlamaIndex RouterQueryEngine
  https://developers.llamaindex.ai/python/examples/query_engine/routerqueryengine/
- LangChain RunnableBranch
  https://reference.langchain.com/javascript/classes/_langchain_core.runnables.RunnableBranch.html

[Stopping Policy Candidate — Experimental Only]
- Stop-RAG
  https://arxiv.org/abs/2510.14337
  https://github.com/chosolbee/Stop-RAG

[Offline Evaluation — Phase 2E default]
- Ragas
  https://github.com/vibrantlabsai/ragas
  https://docs.ragas.io/en/latest/

[Tracing / Observability — Phase 2E default]
- TruLens
  https://github.com/truera/trulens
  https://www.trulens.org/
```

---
