Phase 1 v1.1：L0→L1 证据定位底座（DocumentSnapshot + Chunk/Sentence Index + Gate1）
0. 本阶段新增的硬规则（必须写死）
R1) evidence_quote 必须从文本中截取，禁止 LLM 生成/改写

目的：Gate1 的“quote 可复现”才有意义，否则会被 LLM 改写造成大量伪失败。

写死规则：

BuildFactsIndexNode v2 在拿到 doc_ref(sentence_ids/offsets) 后，由程序从 cleaned_text 截取原文作为 evidence_quote。

quote_hash 必须由程序对 normalize(quote) 计算；quote_normalizer_version 版本化（见 R2）。

这样 Gate1 失败就真的是“索引/切分/抽取定位”的问题，而不是“LLM 改写”的问题。

R2) 归一化/清洗（normalization）必须变成显式版本资产

你已经有 cleaner_version / sentence_splitter_version，Phase 1 再补一个：

写死：

Gate1 的 substring/近似匹配必须使用同一套 normalization_spec（空白、全半角、Unicode NFKC、标点归一、换行合并等）。

normalization_version 记录进 DocumentSnapshot（或 extraction_version 子字段）+ run_record.enabled_policies_snapshot。

quote_hash、sentence_text_digest 都必须基于同一 normalization_version。

（提取器 trafilatura/jusText/readability 输出风格不同，没统一 normalization，Gate1 会很“玄学”。trafilatura/jusText/readability 都是成熟开源入口，可做 fallback。）

R3) Phase 1 doc_id 允许 run-scoped，但要预留 doc_key/doc_version_id 的 preview 字段

Phase 2 要做 doc_version/CDC，Phase 1 现在“顺手算但不启用”，几乎零成本，能大幅降低迁移痛苦。

写死：

doc_id（run-scoped）照旧

额外计算并存储：

doc_key_preview = hash(final_url)

content_hash = hash(cleaned_text_after_normalization)

doc_version_id_preview = hash(doc_key_preview + content_hash)

R4) Sentence 切分：默认规则分句（中英分策略）+ 可选 BlingFire 后端

BlingFire 很快但你们有中文混排/社媒标点等，Phase 1 默认规则分句更稳，BlingFire 仅作为 optional backend。BlingFire 的官方仓库在这里。

写死：

默认：rule-based splitter（中英文标点策略）→ sentence_splitter_version="rule_vX"

可选：sentence_splitter_backend="blingfire" → sentence_splitter_version="blingfire@<ver>"

两者都必须写入 DocumentSnapshot（否则回放对不上）

R5) Gate1 的 key_claim 判定不猜：直接复用 Phase 0 sidecar/structured_report 的 role

你 Phase 0 已经把 lint 从“猜文本”改成“只看结构化 sidecar”，Phase 1 必须延续这条红线。

写死：

Gate1 读取 structured_report.json（或 report_citations.json）中 items[].role

Gate1 对 role=key_claim 的 evidence 定位失败 → SOFT

非 key_claim evidence 定位失败 → WARN

不再写任何“正则猜关键句”的逻辑

R6) Chunking：固定参数 + 锁版本 + 配置快照入档

你继续用 LangChain 的 RecursiveCharacterTextSplitter 没问题，但必须“参数固定+入档”，否则 chunk_id 会漂。官方文档见这里。

写死：

splitter_name + splitter_version + splitter_params(chunk_size/overlap/separators/length_fn) 必须记录到：

run_record.enabled_policies_snapshot

DocumentSnapshot（或 IndexManifest）

chunk_id 生成必须只依赖“固定切分器配置 + normalized cleaned_text”

1. Phase 1 目标（不变，但更可执行）
1.1 产物目标（写死）

DocumentSnapshot：清洗后全文 + 元信息 落盘可离线复核

ChunkIndex + SentenceIndex：可定位索引（chunk_id/sentence_id/offsets/digests）

facts_index.json v2：每条 evidence 必须带 doc_ref（doc_id + chunk_id + sentence_ids/offsets）

Gate1：Evidence Locatability 审计（只读结构化产物）+ 输出 gate1_report.json 与最小 metrics_summary.json

仍保证产出：Gate1 默认 WARN/SOFT，不把系统卡死

2. LangGraph 节点流（Phase 1 更新版）

新增/增强节点顺序（写死）：

FetchDocsNode（现有/增强）

ExtractMainTextNode（增强：可插拔 fallback）

BuildDocumentSnapshotNode（新增：确定性落盘 + preview 字段）

ChunkAndSentenceIndexNode（新增：确定性切分 + 版本化）

BuildFactsIndexNode v2（增强：doc_ref 第一等公民 + 程序截取 quote）

FinalizerStructuredNode（Phase 0 既有）

ValidateStructuredReportNode（Phase 0 既有）

RenderMarkdownNode（Phase 0 既有）

Gate2AuditNode（Phase 0 既有）

Gate1EvidenceAuditNode（新增：引用的关键证据可定位/可复现）

ArchiveRunNode（增强：归档 documents/indexes/gate1/metrics）

边界红线再写一遍：

Finalizer 只消费 allowed_events/facts_index 卡片，不读全文

BuildFactsIndex v2 必须在 Index 之后执行，且 evidence_quote 必须程序截取

3. 数据模型最小 schema（Phase 1 补强版）
3.1 DocumentSnapshot（新增字段补丁）

在你之前的最小字段基础上，追加这些（为 Phase 2 铺路）：

normalization_version（R2）

content_hash（基于 normalized cleaned_text）

doc_key_preview

doc_version_id_preview

sentence_splitter_backend + sentence_splitter_version（R4）

chunk_splitter_name/version/params（或写入 IndexManifest）（R6）

3.2 EvidenceRef（facts_index.v2 中 evidence 的 doc_ref：写死）

doc_ref: {doc_id, chunk_id, sentence_ids[], offsets?}

evidence_quote（程序截取原文）

quote_hash（基于 normalize(quote) + normalizer_version）

若无法定位（Phase 1 允许），必须写：

unlocatable_reason（枚举：extract_failed / non_text / social_post / paywall / dynamic_page / other）

4. Gate1（Phase 1 版）：Evidence Locatability Check（更新版）
4.1 Gate1 输入（写死）

facts_index.json v2

structured_report.json（用于 role=key_claim 分级，不猜）

DocumentSnapshot store + indexes（run 包内）

4.2 Gate1 核心检查（写死）

doc_ref 可解析：doc_id/chunk_id/sentence_ids 合法

quote 可复现：程序截取的 quote 必须能在 sentence 拼接文本中复现（允许近似匹配，但必须使用同一 normalization_version）

对 role=key_claim：若没有任何 locatable evidence，则必须有 unlocatable_reason（否则 SOFT）

4.3 Gate1 severity（写死）

key_claim 引用的 event：no_locatable_evidence AND no_unlocatable_reason → SOFT

非 key_claim：定位失败 → WARN

Phase 1 默认不新增 HARD（避免卡产出）

5. PR 拆解（按你 6 点要求调整后的版本）
P1-PR0：Schemas + 配置快照契约

schemas：DocumentSnapshot/ChunkMeta/SentenceMeta/facts_index_v2/gate1_report/metrics_summary

configs：normalization_spec.yaml + quote_normalizer_version

run_record：必须记录 splitter/sentence/normalization 版本与参数快照（R2/R4/R6）

P1-PR1：ExtractMainTextNode（fallback 依赖池不变）

trafilatura（主/备选之一）

jusText（备选）

readability-lxml（备选）

输出统一格式 + extractor_version + doc_quality_flags

P1-PR2：BuildDocumentSnapshotNode（加 preview 字段）

落盘 cleaned_text（text_ref）+ text_digest

计算并写入 doc_key_preview/content_hash/doc_version_id_preview（R3）

P1-PR3：ChunkAndSentenceIndexNode（固定参数+版本化）

chunk：RecursiveCharacterTextSplitter（参数写死/入档）

sentence：rule-based 默认；BlingFire optional backend（入档版本）

P1-PR4：BuildFactsIndexNode v2（最关键补强：quote 由程序截取）

evidence 必须先绑定 doc_ref（sentence_ids 优先）

evidence_quote 必须从 cleaned_text/句子文本中截取（R1）

quote_hash 基于 normalization_version（R2）

生成 allowed_events 卡片：{event_id, quote, url, doc_ref, credibility_tier}

P1-PR5：Gate1EvidenceAuditNode（按 sidecar role 分级）

读取 structured_report role=key_claim（R5）

输出 gate1_report + metrics_summary（带 key_claim_locatable_rate）

P1-PR6：ArchiveRunNode（R1-lite 归档）

归档 documents/indexes/gate1/metrics

提供离线脚本 verify_locatability（复核某 event 的 quote 定位）

6. Phase 1 DoD（你提的“硬条件”我已写死）

必须通过：

facts_index_v2 / DocumentSnapshot / indexes schema-valid

Gate1 可运行并产出 gate1_report + metrics_summary

硬条件（新增，防空壳）：

structured_report.items[role=key_claim] 引用到的每个 event_id：
至少 1 条 evidence 有 doc_ref，或明确给出 unlocatable_reason（并在 gate1_report 列出缺口清单）

建议达标（阶段完成指标，不硬挡产出）：

key_claim_locatable_rate >= 0.80（可按你们真实主题调参）

extractor_failure_rate、doc_quality_flags 有分桶统计