Phase 0：契约先行（Structured → Render + facts_index + Gate2 severity）

## 当前进度（已完成 Phase 0）

以下 Phase 0 的主链路与 DoD（6.1）已在代码中落地（并有 contracts 测试锁定）：

- Gate2 severity 外置配置：`configs/gate2_severity_phase0.yaml`（`must_be_key_claim` 当前默认 `DISABLE`，测试用例仍覆盖该规则）
- Phase0 结构化产物：`facts_index.json`、`structured_report.json`、`report_citations.json`、`gate_report.json`
- 确定性渲染产物：`final_report.md`（由结构化产物渲染，不依赖 LLM 直接生成 Markdown）
- 归档与可回放：`src/graph/nodes/archive_node.py` 输出 `data/runs/{run_id}/...` + `run_record.json`
- 状态字段显式化：`src/graph/state_v2.py` 已包含 `run_record_path`、`enabled_policies_snapshot`
- 合同与门禁测试：`schemas/*.schema.json` + `tests/contracts/test_phase0_contracts.py`

快速验收命令：

- `conda activate Album; python -m pytest tests/contracts/test_phase0_contracts.py -v`
- `conda activate Album; echo "" | python run_deeptrace_v2.py`

0. 背景与目标
0.1 Phase 0 要解决的核心痛点

报告事实不可验证、不可追溯（无法回答“这句话证据是哪条？”）

finalizer/报告链路容易被硬编码/标注作弊掏空（把所有句子标 analysis）

没有统一的机器可读产物，导致审计/回归/对比都做不实

0.2 Phase 0 的目标（写死）

Finalizer 必须先输出结构化报告 structured_report.json（items 数组 + 引用信息）

final_report.md 必须由 renderer 确定性生成（不依赖 LLM Markdown 一次生成）

Gate2 只读结构化产物（structured_report.json/report_citations.json + facts_index.json），不解析 final_report.md

引入过渡闭环 facts_index.json（硬合同），让 “event_id 引用不是空壳” 在 Phase 0 就成立

建立 severity（WARN/SOFT/HARD）制度：Phase 0 保证能产出报告（除非触发极少数 HARD）

0.3 非目标（Phase 0 明确不做）

不做 doc_key/doc_version_id、chunk/sentence 定位、CDC diff、Timeline merge、breadth×depth、VerificationQueue、Syndication 聚类（这些留到 Phase 1/2/3）

1. 关键定义（防误解）
1.1 event_id 在 Phase 0 的范围（写死）

Phase 0 的 event_id 是 run-scoped：只要求“同一次运行内可闭环验证”，允许 uuid。

Phase 1/2 才追求稳定 event_id（语义 hash / 归一化）与 CDC。

Gate2 在 Phase 0 不对跨 run 稳定性做任何要求。

1.1.1 禁止 LLM 自造 event_id（写死）

FinalizerStructuredNode 不得生成新的 event_id；只能引用 BuildFactsIndexNode 产出的 facts_index.json 中已存在的 event_id 集合（记为 allowed_event_ids）。

实现口径（写死）：Finalizer 的提示词里必须显式提供 allowed_event_ids（或提供可选 event_id 列表/映射），并要求每个 item.event_ids 只能从该集合中选择；若无法找到可支持的证据闭环，则该 item 不能以 key_claim 形式输出（可降级为 analysis/support 且不填/少填 event_ids）。

1.2 判定单位：item（要点）而不是 sentence（写死）

Phase 0 的“关键结论判定单位”是 structured_report.items[]（段落要点 / bullet item），而不是自然语言句子。

这样避免当前 Markdown 输出没有稳定句界导致 must_be_key_claim 误报/漏报。

2. Phase 0 的 LangGraph 节点流（稳定主链路）

你们当前更接近 LangGraph 节点流，Phase 0 推荐按“facts_index 在 finalizer 前、finalizer 输出结构化、render 确定性、gate2 只读结构化”的顺序插节点。LangGraph 的图式 agent/workflow 组织方式本身就适合这种“强产物 + 门禁”流水线。 
GitHub
+1

2.1 建议的节点与顺序（Phase 0）

Research/AggregateEvidenceNode（现有）

BuildFactsIndexNode（新增，确定性） → 输出 facts_index.json

FinalizerStructuredNode（改造：仅输出结构化 JSON） → 输出 structured_report.json

RenderMarkdownNode（新增：确定性渲染） → 输出 final_report.md

ExportSidecarNode（新增：确定性导出） → 输出 report_citations.json

Gate2AuditNode（新增：只读审计） → 输出 gate_report.json

ArchiveRunNode（新增：R0 归档） → 输出 run_record.json + 产物归档目录

核心原则：facts_index 不得在 finalizer 内生成；finalizer 不得“自证其证据”。

2.2 GraphState（Phase 0 最小状态字段）

（你们可用 TypedDict/Pydantic/Dataclass；关键是字段名写死，避免漂移）

run_id: str

evidence_store: …（现有聚合产物，结构不强约束）

facts_index_path: str

structured_report_path: str

report_md_path: str

report_citations_path: str

gate_report_path: str

run_record_path: str

cost: {tokens?, calls?, latency_ms?}（占位即可）

enabled_policies_snapshot: dict（Phase 0 记录开关：severity 配置版本等）

3. Phase 0 的“硬合同产物”（Schemas + 生成责任）

Phase 0 的核心就是“产物契约”。以下 3 个合同必须在 Phase 0 就写死，并在 CI 校验。

3.1 facts_index.json（硬合同，必须在 finalizer 前生成）

生成责任（写死）：BuildFactsIndexNode 生成；Finalizer 只消费。

最小 schema（必须字段）

run_id

generated_at

facts[]：每个 fact：

event_id

evidences[]（至少 1 条，否则该 event_id 不允许被引用）

url

evidence_quote

credibility_tier（枚举见 3.4）

retrieval_ts

doc_ref?（Phase 0 可是 url 或内部 doc 句柄；Phase 1 起再升级）

Phase 0 Gate2 的硬要求

sidecar 引用的 event_id 必须存在于 facts_index

且 evidences.length >= 1

3.2 structured_report.json（硬合同：先结构化，再渲染）

生成责任（写死）：FinalizerStructuredNode 生成（LLM 输出 JSON）。

生成约束（写死）：structured_report.items[].event_ids 只能来自 allowed_event_ids（facts_index.facts[].event_id）。任何不在 facts_index 中的引用都视为“凭空引用”。

JSON 有效性与恢复策略（写死）

- FinalizerStructuredNode 必须实现“解析失败可恢复”的固定流程：解析失败 → 反馈错误并要求 LLM 仅修复为合法 JSON → 重试 N 次（N 写死为小常数，例如 2）。
- 若多次修复仍失败：必须走确定性降级，产出 schema-valid 的 structured_report.json（例如空 sections/items + 明确记录 generation_error），并在 gate_report.json 中给出 HARD_FAIL，避免“无结构化却继续渲染/审计”的隐性乱序。

最小 schema（必须字段）

report_id, run_id, generated_at

generation_errors?（可选：用于记录 JSON 修复/降级原因，便于审计与回归）

sections[]

section_id, title

items[]（Phase 0 判定单位）

item_id: int

item_text: str（建议 ≤ 240，或另设 excerpt）

role: key_claim|support|analysis

event_ids: string[]

assertion_strength: hedged|neutral|strong

dispute_status: none|disputed|unresolved_conflict

conflict_group_id?

“不后处理猜结构”在工程上真正可行的版本就是：结构化 JSON 为源，后面全部确定性派生。

3.3 report_citations.json（硬合同：从 structured_report 确定性导出）

生成责任（写死）：ExportSidecarNode（纯确定性 transform）。

最小 schema

可与 structured_report.items[] 同构（推荐），至少包含：

item_id, item_text, role, event_ids, assertion_strength, dispute_status, conflict_group_id?

这样 Gate2 可以只读 report_citations（或直接读 structured_report），不需要碰 final_report.md。

3.4 枚举表（Phase 0 写死，防口径漂移）

credibility_tier：official | primary | reputable_media | corporate | blog | forum | social | aggregator

verification_status（Phase 0 可选，不强依赖）：unverified | candidate | verified | disputed

Phase 0 的 credibility_tier 必须做 adapter 对齐你们现有来源口径；Gate2 只用于统计与强断言提示，不用于复杂裁决。

4. Gate2（Phase 0 版）：反作弊 + 能产出（severity 制度）
4.1 Gate2 输入/输出（写死）

输入：report_citations.json（或 structured_report）+ facts_index.json
输出：gate_report.json（含 violations + severity + 汇总统计）

Gate2 不读 final_report.md，确保“模板/渲染变化”不影响审计。

4.2 must_be_key_claim（反“role 低报”作弊）

Gate2 对每个 item_text 跑保守检测 must_be_key_claim：

日期/时间模式

数字/比例/金额/排名

状态词（发布/取消/批准/否认/上线/暂停/恢复…）

因果词（因为/导致/因此/归因/责任…）

规则（Phase 0）

must_be_key_claim==true 且 role!=key_claim → WARN（不挡产出，但计数 + 列表）

Phase 2 才升级为 SOFT_FAIL（已在总规划里明确硬化曲线）。

4.3 Phase 0 的 HARD 规则（极少、且与抓取稳定性无关）

只保留两类 HARD（你说的正确原则）：

HARD-1 disputed 语言边界

dispute_status != none → assertion_strength 必须 hedged

dispute_status != none → event_ids.length >= 2 或 conflict_group_id != null

HARD-2 disputed 下强断言禁用词

item_text 命中强断言词表（confirmed/已证实/官方已确认/可以确定…）且 dispute_status != none → HARD_FAIL

其余缺口一律 WARN/SOFT，只输出 gate_report.json（Phase 0 不挡产出）。

4.4 Gate2 的 severity 配置（写死为可配置文件）

建议落成：configs/gate2_severity_phase0.yaml

每条 rule_id 绑定 severity

Phase 0 使用这份配置，Phase 1/2 再换配置（避免硬编码到脚本里）

5. PR0–PR5（LangGraph 代码落地映射清单）

下面按你要的“一一映射”把每个 PR 对应到节点与产物。

PR0：脚手架 + 合同落盘 + CI 骨架

新增

schemas/：facts_index / structured_report / report_citations / gate_report

docs/contracts/phase0_output_contract.md

CI：schema 校验 + gate2_lint 单测框架

不改业务节点

PR1：FinalizerStructuredNode（结构化先行）+ RenderMarkdownNode（确定性渲染）

改造/新增节点

改造 Finalizer → FinalizerStructuredNode：只产出 structured_report.json

补齐 Finalizer 的 JSON 解析失败恢复（固定重试次数 + 最终确定性降级产物）

新增 RenderMarkdownNode：structured → final_report.md（确定性）

新增 ExportSidecarNode：structured → report_citations（确定性）

这一步是 Phase 0 成败关键：做到了，sidecar 就不是事后补丁。

PR2：BuildFactsIndexNode（明确在 finalizer 前）

新增节点

BuildFactsIndexNode：从聚合 evidence/eventnode 生成 facts_index.json（确定性）

在 LangGraph 接线：AggregateEvidence → BuildFactsIndex → FinalizerStructured

PR3：Gate2AuditNode（只读 structured/sidecar + facts_index）

新增节点

Gate2AuditNode：读取 report_citations + facts_index → 输出 gate_report

内含 must_be_key_claim + severity（Phase 0 配置）

PR4：fixtures + 单测 + 回归样例

新增测试资产

tests/fixtures/phase0_pass/

tests/fixtures/phase0_warn_low_report/

tests/fixtures/phase0_fail_disputed_not_hedged/

tests/fixtures/phase0_fail_disputed_strong_word/

单测确保 rule_id/severity 命中稳定

PR5：ArchiveRunNode（R0 RunRecord 归档）

新增节点

ArchiveRunNode：输出 run_record.json，归档本次 run 的：

structured_report / final_report.md / report_citations / facts_index / gate_report

目录建议：runs/{run_id}/…

6. Phase 0 验收（DoD：保证“能产出 + 缺口可见 + 反作弊有效”）
6.1 必须通过（否则 Phase 0 不算完成）

structured_report.json schema-valid

facts_index.json schema-valid

final_report.md 由 renderer 生成（可在 run_record 标记 renderer_version）

Gate2 产出 gate_report.json

HARD 规则可正确阻断：

disputed 未 hedged

disputed 下强断言禁用词

6.2 允许不达标但必须可见（Phase 0 只 WARN/SOFT）

key_claim 引用覆盖率 < 100%（允许）

must_be_key_claim 低报（允许但必须在 gate_report 统计）

facts_index 中 credibility_tier 不完善（允许，但必须统一 adapter 口径）

7. 工具与后续接入点（Phase 0 不强接入，但写入计划与链接）

Phase 0 不把评估/观测工具纳入 DoD，但必须在文档里写清：后续最小闭环选型已定（避免 Phase 2.5 再争论）：

离线评估：Ragas（Phase 2.5/4 接入） 
GitHub
+2
docs.ragas.io
+2

tracing/观测：TruLens（Phase 4 接入） 
GitHub
+2
trulens.org
+2

LangGraph 参考（你们架构基座） 
GitHub
+2
LangChain 文档
+2

链接统一放这里（便于复制进 Phase0.md）

LangGraph:
  https://github.com/langchain-ai/langgraph
  https://docs.langchain.com/oss/python/langgraph/overview
  https://github.com/langchain-ai/langgraph-101

Ragas (offline eval):
  https://github.com/vibrantlabsai/ragas
  https://docs.ragas.io/en/latest/
  https://docs.ragas.io/en/latest/references/

TruLens (tracing/evals):
  https://github.com/truera/trulens
  https://www.trulens.org/
  https://github.com/truera/trulens/tree/main/examples
