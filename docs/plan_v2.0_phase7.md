  # DeepTrace 进阶迭代计划 (Plan v2.0)

## 背景与现状
DeepTrace 目前已完成 MVP 阶段（Phase 1），具备了基于 SerpAPI 的全网事件搜索、结构化事件提取、叙事性报告生成以及初步的内容深挖能力。

**已实现的核心能力：**
- ✅ **通用搜索**：SerpAPI 接入，规避反爬。
- ✅ **深度抓取**：`ContentScraper` 可抓取网页正文。
- ✅ **智能报告**：双模式报告（结构化+叙事）。
- ✅ **鲁棒性**：完善的错误处理和重试机制。

**存在的关键缺口（本次迭代重点）：**
1. **评论挖掘缺失**：目前仅分析正文，缺乏对舆论、观点、争议的深度洞察。
2. **时间线冗余**：多源报道导致同一事件重复出现，缺乏语义去重。
3. **平台特化不足**：缺乏针对特定平台（如小红书/微博）的深度元数据解析。
4. **停止策略简单**：缺乏基于“信息增益”的智能停止机制。

---

## 迭代目标：深度分析闭环 (Deep Analysis Loop)

本阶段的核心目标是**从“新闻聚合”进化为“舆情侦探”**，通过 LLM 强大的理解能力，从现有数据中挖掘出更深层的线索（评论/观点），并清洗数据（去重），最终实现智能化的自动分析流程。

---

## 详细实施计划

### 1. 评论挖掘 (Comment Mining) —— 核心突破口

**策略调整**：
放弃编写脆弱的 HTML 评论区解析器，转而使用 **LLM 智能提取 (LLM-based Extraction)**。利用 LLM 阅读已抓取的 `full_content`，从中提取“文中引用的网友评论”、“官方回应”、“专家观点”等。

> **边界说明**：本阶段只从正文 `full_content` 中抽“类评论信息”（观点/引语/立场），**不试图通用解析各网站真实评论区 HTML**。平台特化（如专门爬取小红书评论区）留给 Phase 8。

#### 1.1 新增 `CommentExtractor` Agent
- **输入**：`Evidence` 对象（含 `full_content`）。
- **Prompt 设计**：
  - 目标：从正文中提取三类信息：
    1. **Public Opinion** (网友热议/舆论倾向)
    2. **Direct Quotes** (当事人/官方直接引语)
    3. **Controversy** (争议点/冲突观点)
  - 输出格式：结构化 JSON List。
- **输出**：`List[Comment]` 对象。

#### 1.1.5 Comment 模型约定
为了确保 `CommentExtractor` -> `CommentTriage` -> `Evidence` 链路的统一性，定义如下 `Comment` 结构：

```yaml
Comment:
  - id: str
  - author: Optional[str]
  - role: Literal["public_opinion", "direct_quote", "controversy"]
  - content: str
  - source_evidence_id: str
  - source_url: Optional[str]
  - meta: Optional[dict]  # e.g. {"likes": 5321}
```

#### 1.2 接入 `CommentTriage`
- 将提取出的 `Comment` 对象喂给现有的 `CommentTriage` Agent。
- **打分逻辑**：评估这些观点是否提供了新线索（Novelty）、是否与现有事实冲突（Contradiction）。
- **晋升机制**：高分观点自动晋升为 `Evidence`，参与后续的时间线构建或驱动新一轮检索。

#### 1.3 Evidence 模型增强
为了支持后续的分析和调参，在 `Evidence` 模型中显式增加以下字段：
- `full_content`: `Optional[str]` (已添加)
- `content_source`: `"snippet" | "full" | "mixed"` (标识内容来源)
- `fetch_status`: `Optional[str]` (`"ok" / "timeout" / "blocked" / "non_html"`)

---

### 2. 时间线去重 (Timeline Deduplication) —— 数据清洗

**策略**：
在 `TimelineBuilder` 阶段引入**语义合并 (Semantic Merging)** 逻辑。

#### 2.1 实现 `deduplicate_events` 算法
- **预处理**：按日期（Day）对事件分组。
- **相似度计算**：
  - **Level 1 (快速)**：Jaccard 相似度或编辑距离（针对标题）。
  - **Level 2 (精准)**：LLM 判断（"这两个事件描述的是同一件事吗？"）。
  - **成本保护**：仅当 **Level 1 相似度 ≥ 0.6** 时，才调用 LLM 做 Level 2 判断，防止 Token 消耗膨胀。
- **合并策略**：
  - **时间**：保留更精确的时间。
  - **标题/描述**：保留信息量最大（最长）的描述。
  - **证据**：合并 `evidence_ids` 列表（Union）。
  - **置信度**：取最大值。

---

### 3. 平台特化 (Platform Specifics) —— 差异化分析 (推迟到 Phase 8)

> **Phase 8 (未来)**：针对单一平台（如小红书或微博）实现特化评论抓取，**不做全网通用评论爬虫**。
> - **目标**：只针对 1 个优先平台，实现专用 Fetcher。
> - **功能**：Top-N 高赞评论抓取，解析结构化字段 (id, author, likes, content)。

---

### 4. 智能停止策略 (Smart Stop Strategy) —— 效率优化

**策略**：
引入 **信息增益 (Information Gain)** 概念，替代死板的 `max_loops`。

#### 4.1 定义信息增益 (GainScore)
定义极简伪公式：

```
GainScore = w1 * 新增事件数
          + w2 * 新增高分评论数
          + w3 * 置信度平均提升值
```

*初始参数建议：w1 = 1.0, w2 = 0.5, w3 = 2.0*

#### 4.2 动态决策逻辑 (`judge_node`)
- 计算本轮 `GainScore`。
- **阈值判断**：
  - 如果 `GainScore < Threshold` 且 `Loop > Min_Loops` -> **停止**。
  - 如果 `GainScore` 很高 -> **继续**（即使接近 Max_Loops，也可申请额外预算）。
- **数据记录**：同时将每轮的 `GainScore` 及其组成部分（`new_events`, `new_high_score_comments`, `avg_confidence_delta`）记录到 `run_stats.jsonl` 中，以便后续调参和评估。

---

## 执行路线图 (Roadmap)

> **前置假设**：Phase 6（深度内容抓取）已稳定可用，Evidence 中的 `full_content` 字段有足够数据。

### Phase 7.1: 评论挖掘闭环 (预计 2 天)
> **依赖**：Phase 6 的 `full_content` 已可用。
- [ ] 实现 `CommentExtractor` Agent (Prompt + Logic)。
- [ ] 修改 `extract_node`：并行运行 Event 和 Comment 提取。
- [ ] 联调 `triage_node`：确保提取的评论能正确打分并晋升。

### Phase 7.2: 时间线优化 (预计 1 天)
> **说明**：可在 7.1 前后并行，但建议在有更丰富事件后验证效果。
- [ ] 实现 `deduplicate_events` 函数。
- [ ] 集成到 `TimelineBuilder`。
- [ ] 验证合并效果（对比优化前后的报告）。

### Phase 7.3: 智能控制 (预计 1 天)
> **依赖**：7.1 / 7.2 已经产出合理的 stats 数据。
- [ ] 升级 `should_continue` 逻辑，加入信息增益判断。
- [ ] (平台特化已推迟)

---

## 预期成果
完成上述迭代后，DeepTrace 将具备：
1. **舆论洞察力**：不仅知道“发生了什么”，还知道“大家怎么看”。
2. **精炼报告**：消除重复信息，阅读体验大幅提升。
3. **智能决策**：自动判断何时该停，何时该深挖，节省 Token 和时间。
