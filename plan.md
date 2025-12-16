## 项目迭代计划（plan.md）

### 背景 & 本迭代目标

我们要实现的是一个 **“侦探式事件链深挖系统”**，  
优先支持小红书场景，通过按需检索 + 评论驱动深挖的方式，在有限数据下还原事件的起因–经过–关键节点–结果。

本轮迭代目标：  
先做出一个 **可以从单一平台（例如小红书 / 或本地模拟数据）中，围绕一个事件问题生成事件链初稿 + 一轮评论驱动深挖** 的 MVP。

---

### 阶段 0：环境 & 项目骨架

- [ ] 选定技术栈（Python + 哪个 Web 框架/CLI + LangGraph/自研 Agent 框架 等）
- [ ] 初始化仓库结构（含 `docs/`、`src/`、`tests/`）
- [ ] 配置基础依赖（LLM SDK、HTTP 客户端、简单日志）
- [ ] 预留接口：  
  - [ ] `EvidenceStore` 抽象
  - [ ] `Fetcher` 抽象（爬虫 / API）
  - [ ] `Agent` / 节点执行骨架

---

### 阶段 1：MVP 核心功能

#### 1. 事件问题 → 最小检索 → 事件链初稿

- [ ] 实现一个种子检索器（可以先用假数据 / Mock，将来再接小红书）
- [ ] 实现 EvidenceStore（内存版 / 简单数据库版）
- [ ] 实现 EventExtractor Agent：
  - [ ] 从帖子文本中抽取事件节点（时间/主体/行为）
- [ ] 实现 Timeline 构建逻辑：
  - [ ] 按时间排序节点
  - [ ] 合并重复 / 低价值节点
- [ ] 提供一个简单接口：  
  “输入事件问题 → 输出事件链初稿（JSON + Markdown）”

#### 2. 评论挖掘 & 关键评论识别（Comment-Triggered Retrieval）

- [ ] 实现 CommentFetcher（从帖子中取评论，可以先 Mock）
- [ ] 设计 CommentScore 模型（Novelty / Evidence / Contradiction 等指标）
- [ ] 实现 CommentTriage Agent：
  - [ ] 对评论打分
  - [ ] 选出 Top-K 关键评论并解释“为何关键”
- [ ] 将关键评论写入 EvidenceStore，并标记为“线索型证据”

#### 3. 按需检索规划 & 一轮深挖

- [ ] 实现 RetrievalPlanner Agent：
  - [ ] 读取当前 Timeline + 关键评论
  - [ ] 生成若干定向检索计划（平台 / 关键词 / 时间窗）
- [ ] 实现 TargetedFetcher（可以先对接一个简单搜索源 / 本地数据）
- [ ] 将新抓到的内容加入 EvidenceStore
- [ ] 让 EventExtractor + Timeline 再跑一轮，生成“事件链 v2”

---

### 阶段 2：扩展功能 / 优化

#### 2.1 连接真实平台（优先小红书）

- [ ] 接入小红书爬虫 / SDK（注意频率 & 合规）
- [ ] 为小红书内容设计平台特化字段（笔记类型、点赞数、话题标签等）
- [ ] 对接真实评论数据，调优 CommentScore 规则

#### 2.2 报告输出 & 可视化

- [ ] 设计事件报告模板（Markdown）
- [ ] 增加节点 → 证据的可追溯链接
- [ ] 简单时间线可视化（可以先用文本 + ASCII / 简易前端）

#### 2.3 停止策略 & 增益控制

- [ ] 设计“信息增益”度量（新证据对事件链的影响程度）
- [ ] 定义停止条件：
  - [ ] 缺口数 < 阈值
  - [ ] 连续两轮增加不大
- [ ] 在 Planner 中加入“预算”（本轮最多发起 N 个检索计划）

---

### 阶段 3：多平台 & 多轮推理（可选）

- [ ] 新增微博 / 新闻平台 Fetcher
- [ ] 在 RetrievalPlanner 中增加跨平台策略：
  - [ ] 什么时候优先查小红书
  - [ ] 什么时候需要引入外部媒体 / 公告
- [ ] 增加多轮迭代（>2 轮）能力，并记录每轮事件链版本
- [ ] 考虑引入简单 RL / 评分机制，为 Planner 的策略优化预留空间

---

### 文档与维护

- [ ] 保持 `docs/spec/` 与实际实现同步更新
- [ ] 为核心模块补 tests（尤其是：
  - [ ] EventExtractor
  - [ ] CommentTriage
  - [ ] RetrievalPlanner
- [ ] 记录典型“案例运行日志”，作为后续调优的基准

---

### Phase 20: SOTA Verification Swarm (DeepTrace 2.0) [Current]

- [x] **Data Layer 1: Robust Preprocessing**
    - [x] Embedding Infrastructure
    - [x] TimelineClusterer (Point 8)
    - [x] SourceClusterer (Point 4)
    - [x] SpanExtractor (Point 2)
- [ ] **Agent Swarm Layer 2: Core Logic**
    - [x] Director (Point 3)
    - [x] Writer (Point 6)
    - [x] Critic (Point 5)
- [ ] **Swarm Controller: Loop & Audit**
    - [x] RevisionLoop (Circuit Breaker)
    - [ ] ConsistencyAuditor (Point 7)
    - [ ] Editor (Unresolvable Conflicts)
