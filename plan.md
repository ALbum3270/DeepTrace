
DeepTrace V2 项目计划书（终稿·完整版 vFinal）

timeline-first · 可验证迭代研究 · 双 Gate 自动审计 · 实验门禁上线 · 可回放 · 可评估

0. 背景与共识
0.1 要解决的核心问题

不可验证：报告事实难以逐条追溯来源

易幻觉/扩写：结论漂移，自相矛盾

覆盖/时效不可控：不知道该不该继续检索

冲突处理弱：不同来源矛盾时容易“挑一个写死”

工程治理弱：模块边界不清，实验污染稳定链路

0.2 总原则（写死）

先事实底座、再写报告：TimelineDoc 是唯一事实来源

结构化优先：输出与中间产物可被 lint、可回放

实验驱动上线：任何“旧思想/新策略”必须走 ablation + 门禁，默认不能进稳定链路

1. 目标与 NFR（非功能性强约束）
1.1 项目目标

产出可验证、可追溯的 TimelineDoc（节点带 URL + 证据定位）

报告严格“只读 timeline”，显著降低幻觉与不一致

stop 策略可解释、可控成本

质量门禁（curator / verify / review-revise）让“可信/不可信”显式化

全链路可观测、可回放、可回归

1.2 红线制度（硬规则）

Finalizer 永远不能提升 verified
Finalizer 只能读取 verification_status/credibility_tier 渲染；不得把 candidate/unverified/disputed 写成 verified。推断只能写入 analysis 且标注 unverified/disputed。

lint 不猜文本结构
Finalizer 必须输出 sidecar report_citations.json，Gate2 完全以 sidecar 做引用审计（不靠正则“猜关键句”）。

引用闭环必须成立
报告关键结论句引用 event_id，审计必须能展开到 ≥1 node_id → doc_version_id → chunk → url。

2. Prior Art（成熟方法/开源/论文）→ 映射到模块与阶段（URL 就地嵌入）

用法不是“贴链接”，而是明确“借鉴什么、落到哪”。

2.1 迭代检索骨架（Phase 2）

GPT Researcher：breadth×depth 迭代检索、并发抓取、引用输出（工程参照，Borrow 控制点，不直接复用代码）

https://github.com/assafelovic/gpt-researcher
https://docs.gptr.dev/docs/gpt-researcher/getting-started


落点：FetchBatch、Router、visited_urls

2.2 路由器（Phase 2）

Haystack ConditionalRouter（条件路由 + fallback）

LangChain RunnableBranch（分支执行抽象）

LlamaIndex RouterQueryEngine（多引擎选择范式）

https://docs.haystack.deepset.ai/docs/conditionalrouter
https://reference.langchain.com/javascript/classes/_langchain_core.runnables.RunnableBranch.html
https://developers.llamaindex.ai/python/examples/query_engine/routerqueryengine/


落点：Router（breadth/depth/mixed、verify-first、fallback）

2.3 Stop 策略候选（Phase 2.5：对照/候选，不默认上）

Stop-RAG：value-based stopping（需要轨迹/奖励定义/训练；仅作为 experimental 对照，过门禁再进 curated）

https://arxiv.org/abs/2510.14337
https://github.com/chosolbee/Stop-RAG


落点：ExperimentRunner 的对照策略池

2.4 research→revise（Phase 3）

RARR：先找证据再修订输出（证据源替换为你们的 timeline/doc chunks）

https://arxiv.org/abs/2210.08726
https://github.com/anthonywchen/RARR


落点：Reviewer/Reviser（审 claim-evidence 支持性、归因与一致性）

2.5 VerificationQueue 范式（Phase 3）

FEVER：claim + evidence → SUPPORTED/REFUTED/NEI 的状态机结构
注意：你们 evidence 来源是 web 抓取 DocumentRecord chunks，不是 Wikipedia；独立来源需扣 syndication。

https://fever.ai/
https://github.com/awslabs/fever


落点：VerificationQueue 数据结构与流程

2.6 评估与可观测（Phase 2.5/4）

Ragas：离线评估/回归（权威入口 vibrantlabsai）

TruLens：tracing + feedback functions（定位失败模式）

LangSmith：平台服务但 SDK 开源（如团队 LangChain 栈可选接入）

# Ragas（权威入口）
https://github.com/vibrantlabsai/ragas
https://docs.ragas.io/en/latest/

# TruLens
https://github.com/truera/trulens
https://www.trulens.org/

# LangSmith SDK（可选）
https://github.com/langchain-ai/langsmith-sdk
https://docs.langchain.com/langsmith/home


落点：EvalHarness（Phase 2.5）+ Observability（Phase 4）

2.7 软报警（Phase 2.5 候选）

SelfCheckGPT：一致性采样软报警（不参与 Verified 硬裁决）

https://arxiv.org/abs/2303.08896
https://github.com/potsawee/selfcheckgpt

2.8 回归/单测工具（Phase 2.5/4 建议纳入）
# Promptfoo（回归对比/CI）
https://github.com/promptfoo/promptfoo

# DeepEval（pytest 风格单测）
https://github.com/confident-ai/deepeval

# OpenAI evals（可选框架参考）
https://github.com/openai/evals

# Giskard OSS（鲁棒性/安全测试扩展）
https://github.com/Giskard-AI/giskard-oss

# Arize Phoenix（可选替代 TruLens 的观测平台）
https://github.com/Arize-ai/phoenix

3. 总体架构（Stable Path）

Planner：输出 CoveragePlan（facets）+ 初始 queries

FetchBatch：检索/抓取/清洗/分块（并发/限速；visited_urls + seen_queries；doc_quality_flags）

ExtractEvents：抽取 TimelineNode（证据定位：sentence_id 优先 + span fallback；quote_hash）

MergeTimeline：去重/保留多版本/冲突分组；输出 CDC diff；写入状态（candidate/disputed 等）

EvaluateDelta：coverage_score、独立来源、冲突、时效、成本、增量

Router + StopDecision：多信号 + 否决门；veto 优先；reason_codes 枚举

Finalizer：只读 TimelineDoc 生成 report + sidecar（report_citations.json）

audit_timeline.py：Gate1/Gate2 双审计 + replay 校验 + 违规 fail-fast

4. 数据模型（关键硬化点全部写死）
4.1 DocumentRecord：doc_key + doc_version_id（内容版本族）

doc_key = hash(final_url)

doc_version_id = hash(doc_key + content_hash)

必须字段（最小）：

doc_key, doc_version_id, url, final_url, retrieved_at, content_hash, extraction_version

chunks[]: ChunkMeta

doc_quality_flags[]

syndication_group_id?

sentence_splitter_version（必须版本化）

4.2 ChunkMeta（最小 schema）

chunk_id, section_path, token_len, text_ref

offsets{start,end}?

sentence_index?（sent_id → offsets，可选但推荐）

4.3 TimelineNode：event_id（语义稳定）+ node_id（证据版本）

event_id：语义稳定，不含 span（用于去重/回归/报告引用）

node_id：证据版本（建议 hash(event_id + doc_version_id + quote_hash)；不含 span）

evidence_quote（<=240 chars）

evidence_sentence_ids[]（推荐）/ evidence_span（fallback）

credibility_tier（枚举）

verification_status（枚举）

conflict_group_id?

provenance{round_id, query_id, retriever, model, prompt_version}

4.4 枚举（写死）

credibility_tier：
official / primary / reputable_media / corporate / blog / forum / social / aggregator

verification_status：
unverified / candidate / verified / disputed

状态修改权限（硬规则）：
只能由 MergeTimeline / VerificationQueue / Curator 修改；Finalizer 永不修改。

4.5 CDC（Merge 输出必须可审计 diff）

added_events[]: [{event_id, node_id}]

updated_nodes[]: [{event_id, node_id, fields_changed[], before_digest, after_digest}]

deduped_events[]: [{event_id, merged_into_event_id, rationale}]

conflict_candidates[]: [{type, member_event_ids[], rationale}]

stats: {dup_rate, new_sources, independent_sources_delta, coverage_delta, conflicts_delta}

4.6 “引用闭环”硬规则（必须可执行）

报告默认引用 event_id

审计必须能展开到 ≥1 node_id → doc_version_id → chunk → url

一个 event_id 多个 node_id 时：报告必须说明选择依据（见 7.2），或进入 ConflictGroup 并列呈现

5. “关键结论句”可执行化：sidecar 驱动 Gate2（不猜文本）
5.1 Key Claim Sentence 定义（Finalizer 标注 role）

包含任意 日期/时间、数字（金额/比例/计数/排名）、状态判断（发布/取消/批准/否认/完成/失败）、因果/归因（因为/导致/因此/源于/责任归属）、事实性断言 的句子，都属于关键结论句。

5.2 Finalizer 输出契约（必须）

输出：

report.md

report_citations.json

5.3 report_citations.json（最小 schema）

report_id, run_id, generated_at

paragraphs[]：

paragraph_id

sentences[]：

sentence_id

text_digest

role: key_claim | support | analysis

event_ids[]（role=key_claim 必填）

node_ids[]（可选）

selection_basis（可选：多证据选择理由）

dispute_status: none | disputed | unresolved_conflict

conflict_group_id?

assertion_strength: hedged | neutral | strong

6. Gate1 / Gate2：自动审计规则（必须 fail-fast）
6.1 Gate1：Timeline Quality

每个节点必须：url + evidence_quote + (sentence_ids 或 span) + doc_version_id + provenance

quote 必须可在 chunk 中复现（sentence_id 优先，span fallback）

分句器版本必须一致（sentence_splitter_version 绑定）

6.2 Gate2：Report Quality（sidecar 驱动）

对所有 role=key_claim：

event_ids.length >= 1

每个 event_id 必须能展开到 ≥1 node_id

若句子 assertion_strength=strong 或使用 Verified 语气，则引用集合必须满足 Verified 门槛

若 dispute_status != none：必须 assertion_strength=hedged 且（引用冲突两边的 event 或引用 conflict_group）

7. Verified 与独立来源口径（写死 + 归一化）
7.1 Verified 硬门槛

Verified 仅当满足其一：

≥1 条 official/primary；或

≥2 条 独立来源 一致（不同 publisher_id 且不同 syndication_group_id）

7.2 多证据默认选择优先级（写死，避免漂）

当同一 event_id 挂多个 node_id：

official/primary 且最新 doc_version

≥2 独立来源一致（扣 syndication），优先 reputable_media

单一 reputable_media：只能 candidate/unverified
冲突未解：必须进入 ConflictGroup 并列呈现（禁止挑一个写死）

7.3 publisher_id 归一化（硬规则）

独立来源统计用 publisher_id（不是 domain）

publisher_id 必须来自归一化表：assets/publishers/domain_to_publisher.json（可审计变更）

8. 冲突（ConflictGroup）的报告模板 + disputed 语言边界（防误导）
8.1 报告必须包含固定章节：Conflicts & Disputes

对每个 conflict_group 输出固定结构：

冲突摘要（不下结论）

并列版本表（至少两行，分别引用 event_id）

分歧解释（时间点、定义差异、转载、官方缺失等）

当前状态：disputed/unverified/resolved（由状态机决定）

下一步验证建议（可选，来自 VerificationQueue）

8.2 disputed 允许/禁止句式边界（Gate2）

允许（必须 hedged）：

“Some sources report X, while others report Y…”

“Reports differ on whether…”

“As of {date}, no official confirmation; sources disagree…”

禁止（disputed 下必须 fail）：

“confirmed / officially confirmed / it is certain / definitively / 已证实 / 官方已确认 / 可以确定”等强断言
除非冲突已 resolved 且引用满足 Verified 门槛。

9. replay_pack（可回放）硬化：必须能离线重放证据
9.1 二选一（必须满足其一）

A) 存清洗后 chunks 快照（推荐）
B) 存 raw + cleaner 版本 + 可重复抽取产物（更复杂）

9.2 A 路径存储契约（写死）

text_ref 必须离线可寻址到 replay 包内 chunk 文本

推荐：

replay_pack/{run_id}/manifest.json

replay_pack/{run_id}/chunks/{doc_version_id}.jsonl.zst

CI 无外网条件下可重跑 Gate1/Gate2

10. 文档质量过滤（轻量 Gate1 前置，防队列爆炸）
10.1 doc_quality_flags（最小集合）

too_short / no_main_text / non_text / paywall / duplicate / aggregator_suspected / no_date / no_author

10.2 过滤门槛（写死）

命中 too_short | no_main_text | non_text | aggregator_suspected：

可保留线索

不进入 Verified 候选、不计独立来源一致

引用时默认低 tier + unverified

11. StopDecision：veto 优先级 + reason_codes 枚举（写死）
11.1 reason_codes（最小枚举）

STOP_MAX_ROUNDS / STOP_BUDGET_GUARD / STOP_LOW_DELTA_CONSECUTIVE / STOP_HIGH_DUP_RATE_CONSECUTIVE / STOP_COVERAGE_REACHED / STOP_RECENCY_MET / STOP_NO_NEW_INDEPENDENT_SOURCES / CONTINUE_* / BLOCKED_BY_VETO_*

11.2 优先级规则（写死）

veto 永远优先于 stop signals

若 stop signals 满足但 veto 存在：decision=continue 且 reason_codes 必含 BLOCKED_BY_VETO_*

12. 交付与验收（DoD）+ 时间/资源（按 Sprint）

建议：1 Sprint = 2 周。下面是推荐排期与验收口径（可调整，但 DoD 必须固定）。

12.1 资源编制（两档）

Lean（最小可跑）3 人：Timeline/Pipeline（1）+ Quality/Eval（1）+ Infra/Scrape/Replay（1）
Standard（推荐）5 人：Pipeline（2）+ Quality/Eval（1）+ Infra/Obs（1）+ Retrieval/Scrape（1）

12.2 Phase 0（1 Sprint）：稳定性兜底 + sidecar 契约

交付

Finalizer 输出 report + report_citations.json

Gate2 基于 sidecar 做引用审计（100%）

Finalizer 不提升 verified lint

schema 校验（含 sidecar）

验收

role=key_claim 引用完整率 citation_completeness = 100%

任意 event_id 能展开到 node_id→doc_version→chunk→url

Verified 误用（强断言但不满足门槛）必须被 Gate2 fail

12.3 Phase 1（2 Sprints）：Timeline Engine MVP + CDC + replay A 路径

交付

doc_key/doc_version + event_id/node_id + CDC diff

evidence 定位（sentence_id 优先）

replay_pack A 路径契约（离线可重放）

验收

Gate1：抽样 50 nodes，证据可定位成功率 ≥98%

断网回放：可重跑 Gate1/Gate2 并通过

CDC：重跑 event_id 稳定；更新必须出现在 updated_nodes 且 digest 可追溯

12.4 Phase 2（2 Sprints）：breadth×depth + Router + 去重 + stop（启发式稳定版）

交付

breadth×depth、并发/限速/降级

visited_urls + seen_queries

Router（策略切换）

StopDecision（reason_codes + veto 优先）

验收

固定预算下：dup_rate 降（>=20%），independent_sources_count 不降，coverage_score 不降

veto 阻止 stop 的记录可解释（decision=continue + BLOCKED_BY_VETO_*）

12.5 Phase 2.5（2 Sprints）：实验门禁（ablation runner + 基线 + 阈值）

交付

policy_registry：system/curated/experimental

ablation runner：baseline vs variant（replay_pack 驱动）

evaluation_report（指标+成本+失败样例+边界）

Stop-RAG 仅作为对照候选（experimental）

验收

策略进 curated 必须满足门槛（见 13.3）

每个策略必须产出 ADR（动机/权衡/替代方案/失败样例）

12.6 Phase 3（2–3 Sprints）：质量门禁（Curator + VerificationQueue + Review/Revise）

交付

doc_quality_flags 过滤

syndication 聚类模块（可替换接口）

VerificationQueue（FEVER 状态机）

Reviewer/Reviser（RARR 范式）

验收

verified_misuse_rate < 1%（建议更严 <0.3%）

队列不爆炸（有上限、TTL、去重）

冲突呈现合规率 100%（无“挑一个写死”）

12.7 Phase 4（1–2 Sprints）：可观测性 + CI 回归

交付

tracing（TruLens 或 Phoenix 二选一）

CI 回归：每 PR 跑小回归集（5–10 topics）

运行包归档（rounds + replay_pack + eval_run）

验收

任一失败能定位模块与原因类别

PR 破坏 gate / 指标退化会被 CI 阻止合入

13. 评估体系（基线 + 指标定义 + 数据集/标注策略）
13.1 Baseline（必须固定）

BL0：Phase1 MVP（timeline-first + CDC + gates）

BL1：Phase2 breadth-only

BL2：Phase2 no curator/no syndication（量化 curator/聚类价值）

13.2 指标定义（最小指标集）

从 TimelineDoc/RoundRecord/sidecar 可直接计算：

added_events_per_round = |CDC.added_events|

coverage_score：CoveragePlan facets 加权命中

independent_sources_count：按归一化 publisher_id 去重，且扣 syndication_group

recency_best_days：min(now - published_at)（无 published 用 retrieved fallback）

citation_completeness = key_claim 句子引用 event_id 的比例（期望 100%）

evidence_locatability = quote 可定位比例（期望 ≥98%）

verified_misuse_rate：强断言但不满足 Verified 门槛的比例（期望趋近 0）

disputed_presentation_violation_rate：disputed 句子出现强断言/不并列呈现（期望 0）

cost_per_added_event = total_cost / total_added_events

13.3 进 curated 的门槛（写死在 ablation_protocol）

对固定评估集：

citation_completeness == 100%

evidence_locatability >= 98%

verified_misuse_rate <= 1%（推荐 <=0.3%）

disputed_presentation_violation_rate == 0

coverage_score 不下降（<=0.5% 波动可接受）

cost_per_added_event 持平或更优（允许 +5% 若覆盖明显提升）

13.4 数据集与标注（可落地、成本可控）

30–50 topics，覆盖：热点/冷门/强时间线/高争议

每个 topic 先抓取一次生成 replay_pack（冻结证据文本）

人工金标最小化：每 topic 标 5–10 个关键事件 + 少量 conflict/verification（高影响 claim）

双人标注+仲裁（只对高影响项）

14. 评测/验证工具栈（纳入计划，不只是参考）
14.1 EvalHarness（新增模块，统一入口）

输入：replay_pack + TimelineDoc + report.md + report_citations.json
输出：eval_run.json（工具版本、judge 配置、指标结果）+ 回填 MetricsSummary

14.2 工具选择与落点

Phase 2.5 / 4（离线评估与回归）：Ragas

https://github.com/vibrantlabsai/ragas

https://docs.ragas.io/en/latest/

Phase 4（tracing/定位失败）：TruLens（或 Phoenix 二选一）

https://github.com/truera/trulens

https://www.trulens.org/

备选 Phoenix：https://github.com/Arize-ai/phoenix

可选（LangChain 栈接入方便）：LangSmith SDK

https://github.com/langchain-ai/langsmith-sdk

https://docs.langchain.com/langsmith/home

回归对比/CI：Promptfoo

https://github.com/promptfoo/promptfoo

pytest 风格单测：DeepEval

https://github.com/confident-ai/deepeval

扩展（安全/鲁棒）：Giskard OSS

https://github.com/Giskard-AI/giskard-oss