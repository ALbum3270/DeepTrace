你的这些“Phase 2 v1.1 补丁建议”整体是对的，而且方向很关键：它们不是“加功能”，而是在 **Phase 2 这么大 scope** 的情况下，把“能复盘、能回滚、能验收”的硬边界写死，避免最后变成“做了很多，但解释不了/回放不了/不敢合入”。

我会给结论：**建议全部采纳**，但有两处我会做“更工程化的微调”，避免把产出卡死。

## 我对你这份建议的判断（逐条）

### ✅ Patch 1（短 quote 根因）——完全正确，但我建议补一个“允许降级展示”的出口

你写的“锚点前移到 ExtractEvents，LLM 给 doc_version_id+chunk_id+sentence_ids/span，quote 由程序截取；LLM 不得改写 quote”，这是解决 Phase 1 “hint 抽象→difflib 找到 6 字符 quote” 的根治方案。

**微调建议（不改变原则）：**

* “无法给锚点”的 fallback 不要让事件彻底消失，而是：

  * `unlocatable_reason` 必填
  * **禁止**被 `role=key_claim` 引用
  * 允许出现在 `role=support/analysis`，但 **assertion_strength=hedged**，并在 Gate 报告里计数（让你们能追根因：抽取器失败 / 文档非文本 / 社媒无 HTML 等）。

这样既不退回老坑，也不让系统“因为少数不可定位文档而完全出不了东西”。

### ✅ Patch 2（RouterDecision 最小 schema）——必须写死

不写死就会出现：Router 输出漂移、日志不可比较、ablation 也没法对齐。

Router 参考你写得对：Haystack ConditionalRouter ([Ragas][1])、LlamaIndex RouterQueryEngine  都是“条件/多引擎选择”范式。

### ✅ Patch 3（定位前移）——这是 Phase2 的“心脏修复点”

Phase 2 如果不强制 “ExtractEvents 直接产出锚点”，你后面再做 CDC/replay/ablation 只是在放大不稳定性。

### ✅ Patch 4（doc_version 存储语义）——必须补，不然 doc_key/doc_version_id 会“有字段没语义”

你写的两句话（doc_key=族、doc_version=内容版本；latest 指针；CDC 以 doc_version 为证据引用单位）是后续 **“同 URL 多次抓取导致内容变化”** 能被解释的前提。

### ✅ Patch 5（Stop 防抖 + min_rounds）——非常必要

没有连续 K 轮、防抖、min_rounds，Stop 会被偶发 dup_rate/抓取失败误导。你现在的 veto 优先 + reason_codes 枚举是正确方向（Stop-RAG 也确实应该只作为对照候选）。Stop-RAG 论文把迭代 RAG 的停止视作控制问题，并提出 value-based stopping controller，这类方法更适合进入“实验门禁”而非直接上稳定链路。([arXiv][2])

### ✅ Patch 6（publisher_id 口径写死）——必要

否则 independent_sources_count 会被子域/镜像站/转载搞爆，Stop/Verified 信号都被污染。

### ✅ Patch 7（replay_pack manifest 最小集）——必要

不写死就会出现“存了 chunks，但缺 RoundRecord/sidecar/gate 报告”，回放跑不起来，ablation runner 也只能做半截。

### ✅ Patch 8（工具栈先选 1+1 并写死）——建议就这么定

* 离线评估：Ragas（Phase2E 最小接入）([Ragas][1])
* Tracing/观测：TruLens（Phase2E 二选一就先选它）([TruLens][3])

这能避免 Phase2E 又陷入“工具选型争论拖延”。

### ✅ 关于“参考链接修正”的提醒——你提得也对

* GPT Researcher 的 repo 和 docs 可以当“breadth×depth 迭代检索 + 引用输出”的工程参照，但你们要 **Borrow 控制点**，别直接照抄架构。([GitHub][4])
* Haystack/LlamaIndex 的 Router 文档入口也能支撑你把 Router 设计写成 contract（而不是 prompt 工程）。([Ragas][1])

---

# Phase 2 v1.1（完整版·可入 repo 评审稿）

> **Phase 2（包含你原先 Phase 2.5 的“实验门禁/ablation/eval 最小接入”）**
> 目标：在不推翻 Phase 0/1 主链路的前提下，把 **迭代检索工程化**（breadth×depth、Router、Stop、去重）、**演进可审计**（doc_version + CDC）、**可回放可证伪**（replay_pack + ablation runner）、**最小评估/观测闭环**（Ragas + TruLens）一次铺好。

---

## 0. 前置与依赖

### 0.1 依赖 Phase 0（已具备）

* `report.md + report_citations.json`（sidecar）强契约
* Gate2：只基于 sidecar 做关键结论句审计（不猜文本）
* `facts_index.json`（event_id → 至少 1 条 evidence，不空壳）

### 0.2 依赖 Phase 1（已具备）

* DocumentSnapshot（cleaned_text + 元信息 + 版本号占位）
* chunk/sentence 索引（可定位）
* Gate1（Evidence Locatability）已能跑并产出报告

---

## 1. Phase 2 的“写死”交付（DoD 核心）

### 1.1 Orchestration（覆盖↑、重复↓、成本可控）

* breadth×depth 迭代检索（并发池、限速、失败降级）
* visited_urls + seen_queries（query 规范化 + 去重）
* Router（条件/分支/fallback）
* StopDecision（启发式 + veto 优先 + reason_codes 枚举 + 防抖）

### 1.2 Evolution（可审计演进）

* doc_key / doc_version_id 正式 contract
* event_id 稳定化（跨 run）
* Merge 输出 CDC diff（added/updated/deduped/conflict_candidates + digests + 更新来源）

### 1.3 Replay & Falsifiability（可回放、可证伪）

* replay_pack A 路径：存清洗后 chunks 快照 + manifest（断网可回放）
* **最小确定性回放**：离线可重跑 Extract + Merge + Gate + Stop（不要求回放抓取）

### 1.4 Experiment Gate（把“未验证策略”变成可证伪）

* policy_registry：system / curated / experimental
* ablation runner：baseline vs variant（replay_pack 驱动）
* evaluation_report：指标对比 + 成本 + 失败样例
* Stop-RAG 仅作为 experimental 对照候选（过门禁再进 curated）([arXiv][2])

### 1.5 Eval/Tracing 最小接入（不追求全面，只追求闭环）

* Ragas：离线评估最小跑通，产出 eval artifact ([Ragas][1])
* TruLens：最小 tracing/feedback 归档跑通 ([TruLens][3])

---

## 2. Phase 2 内部分解为 5 个可验收子里程碑（仍统称 Phase 2）

* **2A Orchestration 最小闭环**：breadth×depth + Router + 并发/限速 + visited/seen + Stop 落盘
* **2B Version/ID/CDC**：doc_version 家族 + event_id 稳定化 + MergeCDC（含更新来源）
* **2C Replay R1**：replay_pack(A) + 断网回放（Extract/Merge/Gates/Stop）
* **2D Policy & Ablation**：policy_registry + ablation runner + evaluation_report
* **2E Eval/Tracing 最小接入**：Ragas（离线）+ TruLens（Tracing）二者都能产物归档

> 备注：这 5 块都必须 **feature flag** 可回滚；任何一块关掉，Phase 0/1 主链路仍可跑。

---

## 3. Phase 2 “硬规则”（防空壳/防返工）

### 3.1 Evidence 锚点规则（修复短 quote 根因）

* **主路径（硬）**：ExtractEvents 必须返回 `doc_version_id + chunk_id + sentence_ids[]`（优先）或 `span`（fallback）。
* `evidence_quote` 必须由程序从 sentence_ids/span 截取；**LLM 不得改写 quote**。
* **无法锚定时（可见降级）**：必须填 `unlocatable_reason`，且该 evidence **禁止用于 role=key_claim**；只允许 support/analysis，并强制 `assertion_strength=hedged`。

### 3.2 RouterDecision 必须落盘（可复盘）

每轮 RoundRecord 必须同时落盘：

* 输入集合：query_ids、doc_version_ids、enabled_policies_snapshot
* 决策集合：router_decision、stop_decision
* 变化集合：merge_result（CDC + digests）

### 3.3 doc_key/doc_version_id 的系统语义写死

* `doc_key = hash(final_url_canonical)`：文档族
* `doc_version_id = hash(doc_key + content_hash)`：内容版本
* DocVersionResolver 维护 `doc_key -> latest_doc_version_id`（按 retrieved_at 或 published_at 的规则写死）
* CDC/Node 证据引用单位必须是 `doc_version_id`（不是 doc_key）

### 3.4 Stop 决策防抖 + min_rounds（稳定性）

* `STOP_LOW_DELTA_CONSECUTIVE` / `STOP_HIGH_DUP_RATE_CONSECUTIVE` 必须连续 K 轮触发（K=2 或 3，写死默认值）
* 未达到 `min_rounds`：即使 stop signals 满足也必须 continue，并输出 `CONTINUE_MIN_ROUNDS_NOT_MET`
* **veto 优先硬合同**：signals 指向 stop 但 veto 存在 ⇒ `decision=continue` 且 reason_codes 必含 `BLOCKED_BY_VETO_*`

### 3.5 publisher_id 归一化口径写死

* 独立来源统计必须用 `publisher_id`（来自归一化表 domain→publisher）
* domain/subdomain 不允许直接当独立来源口径

### 3.6 replay_pack R1 最小集写死（保证能回放/能 ablation）

R1 至少包含：

* DocumentSnapshot + chunk/sentence indexes（含版本号）
* facts_index_v2.json
* structured_report.json + report_citations.json
* gate1_report.json + gate2_report.json
* RoundRecord[] + StopDecision + MetricsSummary
* replay_manifest.json（列出版本、策略快照、输入路径）

---

## 4. 数据合同（Schemas，Phase 2 需要新增/升级的最小集合）

### 4.1 RouterDecision（新增，写死）

* route: `breadth | depth | mixed | fallback`
* rationale_codes: string[]
* budget_hint: {max_rounds?, max_docs?, max_calls?}
* fallback_route?
* router_version
* enabled_policies_snapshot

### 4.2 StopDecision（升级为闭环合同）

* signals: {new_events, new_nodes, dup_rate, new_sources, recency_best_days, cost_per_new_event? …}
* vetoes: string[]
* decision: `continue | stop`
* reason_codes: string[]（枚举表写死）
* stop_version
* enabled_policies_snapshot

### 4.3 MergeResult / CDC diff（升级）

* added_events[]: {event_id, node_ids[]}
* updated_events[]: {event_id, fields_changed[], before_digest, after_digest, evidence_basis}

  * evidence_basis 枚举：`NEW_DOC_VERSION | NEW_SOURCE | HIGHER_TIER_EVIDENCE | CONFLICT_RESOLUTION | OTHER`
* deduped_events[]: {event_id, dedupe_key, rationale}
* conflict_candidates[]: {conflict_group_id, type, member_event_ids[], rationale}

### 4.4 RoundRecord（写死）

* round_id
* router_decision
* query_ids[]
* doc_version_ids[]
* merge_result
* stop_decision
* cost {tokens, calls, latency_ms}
* enabled_policies_snapshot

### 4.5 policy_registry（新增）

* policy_id、tier(system/curated/experimental)、owner、version、flags、entrypoints、default_on?

### 4.6 ablation_run（新增）

* baseline_policy_id、variant_policy_id
* replay_pack_id / run_ids
* metrics_delta（含 gate_fail_counts）
* pass/fail（curated 晋级判定）
* failure_examples（最少 N 条）

---

## 5. LangGraph 节点流（Phase 2 增量改造，不推翻 Phase0/1）

> 所有新节点必须可通过 feature flags 关闭。

### 5.1 主要节点（按推荐顺序接入）

1. FetchBatchNode（增强并发/限速/降级）
2. CanonicalizeQueryNode（query 规范化 + query_fingerprint）
3. DedupNode（visited_urls + seen_queries + content_hash 去重标记）
4. RouterNode → 输出 RouterDecision
5. ExtractMainText/BuildSnapshot/Index（沿用 Phase 1）
6. ExtractEventsNode（**硬规则：必须产出锚点**）
7. MergeCDCNode（输出 CDC + conflict_candidates）
8. ComputeSignalsNode（生成 stop signals + 派生成本指标）
9. StopControllerNode（防抖 + veto 优先 + reason_codes）
10. FinalizerStructuredNode（只读 facts/timeline，生成 sidecar）
11. Gate2AuditNode（只看 sidecar）
12. Gate1EvidenceAuditNode（定位复现审计）
13. ArchiveRunNode（写入 RoundRecords/Metrics/replay_manifest/replay_pack）

---

## 6. PR/Jira 拆解（建议按 2A–2E 分组推进）

### 2A：Orchestration 最小闭环

* PR2A-0：并发池/限速/失败降级骨架 + feature flags
* PR2A-1：seen_queries（规范化 + fingerprint）+ visited_urls
* PR2A-2：RouterNode + RouterDecision schema + 日志落盘

  * Router 参照：Haystack ConditionalRouter ([Ragas][1])、LlamaIndex RouterQueryEngine
* PR2A-3：StopControllerNode（防抖/min_rounds/veto 优先 + reason_codes）

### 2B：Version/ID/CDC

* PR2B-0：doc_key/doc_version_id 扶正（url_canonicalization_version + normalization_version 写入 Snapshot）
* PR2B-1：event_id 稳定化（event_id_version=v1 + canonicalization 版本化）
* PR2B-2：MergeCDCNode（CDC diff + evidence_basis + digests）

### 2C：Replay R1

* PR2C-0：replay_pack(A) 目录契约 + chunks 快照 + manifest
* PR2C-1：离线 replay 工具（Extract/Merge/Gate/Stop 可跑）+ CI smoke

### 2D：Policy & Ablation（原 Phase 2.5 合并进来）

* PR2D-0：policy_registry（system/curated/experimental）+ enabled_policies_snapshot
* PR2D-1：ablation runner（baseline vs variant，replay_pack 驱动）
* PR2D-2：Stop-RAG 接入为 experimental（不默认启用）([arXiv][2])

### 2E：Eval/Tracing 最小接入

* PR2E-0：Ragas 最小离线评估（对 replay_pack 输出 eval artifact）([Ragas][1])
* PR2E-1：TruLens tracing 最小接入（记录节点级 trace + 归档）([TruLens][3])

---

## 7. 验收（DoD）

### 7.1 必须通过（硬）

* 每次 run 都产出：RoundRecord[] + MetricsSummary + RouterDecision + StopDecision + CDC
* veto 优先可测：出现 veto 时必须输出 `BLOCKED_BY_VETO_*`
* ExtractEvents 锚点规则生效：`key_claim` 引用的 event 必须可定位（否则 Gate2 fail）
* feature flags 回滚：关闭 2A/2B/2C/2D/2E 任一块，Phase0/1 仍可跑

### 7.2 允许不完美但必须可见（软）

* coverage_score 可为空（但字段必须存在）
* independent_sources_count Phase2 先按 publisher_id 去重（syndication 扣除留后续）
* replay_pack 只做到 R1（够用），R2（回放抓取/原始 HTML）不要求

---

## 8. 参照链接在计划里的“放置位置”建议（你问的“应该放哪里用”）

### 8.1 放在“模块小节末尾：Prior Art / Reference Implementation”

好处：读者看到 Router/Stop/ablation 时，立刻知道“你借鉴什么，但落点在哪”，而不是文末一堆链接没人点。

* **breadth×depth / FetchBatch** 小节末尾：放 GPT Researcher（工程参照）([GitHub][4])
* **RouterNode** 小节末尾：放 Haystack ConditionalRouter、LlamaIndex RouterQueryEngine ([Ragas][1])
* **Stop-RAG（experimental）** 小节末尾：放 arXiv + repo ([arXiv][2])
* **Eval/Tracing** 小节末尾：放 Ragas、TruLens ([Ragas][1])

### 8.2 再在文末放一个“Links Appendix（可复制）”

用于 repo 文档里方便复制粘贴（注意：这里用 raw URL 最方便，建议就放 code block）。

```text
GPT Researcher (breadth×depth reference)
  https://github.com/assafelovic/gpt-researcher
  https://docs.gptr.dev/docs/gpt-researcher/getting-started

Router references
  https://docs.haystack.deepset.ai/docs/conditionalrouter
  https://developers.llamaindex.ai/python/examples/query_engine/routerqueryengine/
  https://reference.langchain.com/javascript/classes/_langchain_core.runnables.RunnableBranch.html

Stop-RAG (experimental baseline candidate)
  https://arxiv.org/abs/2510.14337
  https://github.com/chosolbee/Stop-RAG

Ragas (offline eval)
  https://github.com/vibrantlabsai/ragas
  https://docs.ragas.io/en/latest/

TruLens (tracing/eval)
  https://github.com/truera/trulens
  https://www.trulens.org/
```

---

# 最后回答你：这些建议对不对？

**对，而且很值得写进 Phase2.md。**
尤其是 Patch 1/2/3/7/8：它们决定 Phase 2 是“能落地能复盘的工程闭环”，还是“功能堆起来但不可回放的研究原型”。

如果你愿意，我可以把上面这份“完整版”进一步收敛成**仓库内文件结构**（例如 `docs/phases/phase2_v1_1.md`、`schemas/*.schema.json`、`scripts/replay_r1.py`、`scripts/run_ablation.py`），并给每个 PR 生成对应的“目录与产物清单（paths contract）”。

[1]: https://docs.ragas.io/en/latest/ "Ragas"
[2]: https://arxiv.org/abs/2510.14337 "[2510.14337] Stop-RAG: Value-Based Retrieval Control for Iterative RAG"
[3]: https://www.trulens.org/ "TruLens: Evals and Tracing for Agents"
[4]: https://github.com/assafelovic/gpt-researcher "GitHub - assafelovic/gpt-researcher: An LLM agent that conducts deep research (local and web) on any given topic and generates a long report with citations."
