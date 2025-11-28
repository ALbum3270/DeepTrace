## 架构说明（Architecture）

### 1. 架构风格选择

本项目采用 **模块化单体 + LangGraph 状态机** 的架构风格：

- **单体应用**：
  - 所有逻辑在一个代码仓库和一个进程内运行
  - 通过清晰的模块划分（core/fetchers/agents/graph 等）控制复杂度
- **LangGraph 编排**：
  - 将事件分析流程拆成多个节点（Agents）
  - 用 StateGraph 控制执行顺序、条件跳转与多轮迭代

理由：

1. 当前场景是面向“单事件深挖”的分析工具，而非大规模分布式服务
2. 需求尚在探索阶段，频繁重构不可避免，单体更易演化
3. LangGraph 非常适合表达“按需检索 + 多轮推理”的复杂流程

---

### 2. 模块划分与职责

项目主目录（src/）按“领域 + 职责”划分为以下模块：

```text
src/
  config/           # 配置管理（模型、API Key、平台开关等）

  core/             # 领域模型 & 纯业务逻辑（与框架无关）
    models/
      evidence.py   # 证据数据结构
      events.py     # 事件节点 / 未解决问题
      timeline.py   # 时间线结构与排序规则
      comments.py   # 评论与评论打分相关结构
    evidence_store.py # 证据存取接口 & 实现（MVP 内存版）
    scoring.py      # 评论打分、信息增益等算法（规则/启发式）

  fetchers/         # 外部数据源抓取/查询
    base.py         # FetchPlan 抽象 & Fetcher 接口
    xhs_fetcher.py  # 小红书相关抓取（MVP 可用 mock，后续接真实）
    news_fetcher.py # 新闻 / 通用搜索抓取

  llm/              # 大模型调用封装
    client.py       # 统一 LLMClient，屏蔽底层供应商差异
    prompts/        # 各 Agent 的提示词模板
      event_extractor.md
      comment_triage.md
      retrieval_planner.md
      reporter.md

  agents/           # 面向 LLM 的“工具层”逻辑（单个节点责任）
    event_extractor.py    # 帖子/文章 → 事件节点抽取 & OpenQuestions
    comment_triage.py     # 评论打分、选出关键评论
    retrieval_planner.py  # 从缺口 & 关键评论 → 检索计划
    reporter.py           # 根据最终时间线生成报告

  graph/            # LangGraph 状态机编排
    state.py             # GraphState：query/evidence/timeline/预算 等
    event_chain_graph.py # 构建 StateGraph，定义节点与条件边
    judge.py             # 判断是否继续迭代的策略函数
    fetcher_node.py      # 读取 FetchPlan，调用 fetchers 执行抓取

  interface/        # 对外入口（MVP：CLI，将来可以加 HTTP）
    cli.py               # 命令行入口：接受 query，运行 Graph，输出报告
    web_app.py           # 预留：HTTP API / Web UI（后续再实现）
```

#### 层间依赖约束（简要）

* `core/` 不依赖 `agents/`、`graph/`、`interface/`，只依赖标准库和 `llm` 以外纯工具（尽量保持“干净”）
* `agents/` 可以依赖：

  * `core/`（数据模型与业务逻辑）
  * `fetchers/`（如需要同步抓取）
  * `llm/`（调用模型）
* `graph/` 负责把 `agents/` 组合在一起，但自身尽量不写复杂业务，只处理：

  * 状态流转
  * 条件判断
* `interface/` 仅调用 `graph/` 暴露的入口，不直接操作底层模块

---

### 3. GraphState 与主流程概览

#### GraphState（简要）

GraphState 代表“当前一次事件调查”的整体状态，核心字段包括：

* `query`：用户提出的问题（事件描述）
* `evidence_ids` / `evidence_store`：证据集合与存取方式
* `timeline`：当前构建出的事件时间线（EventNode 列表）
* `iteration`：当前迭代轮数
* `pending_fetch_plans`：待执行的抓取计划（FetchPlan 列表）
* `last_comment_scores`：上一轮关键评论打分结果
* `max_iterations` / `fetch_budget`：资源/预算控制
* `logs`：简要的过程日志，便于调试与可视化

> 实际实现中，考虑 LangGraph 对状态可序列化的要求，`EvidenceStore` 等复杂对象可通过外部依赖注入/单例管理，State 中只保存 ID 列表。

#### 主流程（高层节点流向）

1. **event_extractor**

   * 输入：当前已知的核心证据（种子帖子/文章）
   * 输出：

     * 初版 / 更新后的 Timeline（事件节点）
     * 一组 OpenQuestions（尚未解答的问题 / 缺口）

2. **comment_triage**

   * 输入：相关贴子的评论集合
   * 逻辑：对评论进行打分，识别“关键评论”（Novelty/Evidence/Contradiction 等）
   * 输出：

     * `last_comment_scores`
     * 将关键评论标记为“线索型证据”

3. **retrieval_planner**

   * 输入：`timeline.open_questions` + `last_comment_scores`
   * 逻辑：生成最小化的定向检索计划（平台 / 关键词 / 时间窗）
   * 输出：`pending_fetch_plans`

4. **fetcher_node**

   * 输入：`pending_fetch_plans`
   * 逻辑：调用具体 Fetcher（xhs/news…）抓取少量高价值新证据
   * 输出：

     * 新证据写入 EvidenceStore
     * `new_evidence_ids` 更新

5. **event_extractor（再次执行）**

   * 使用新证据重跑抽取与时间线更新，形成 timeline v2/v3…

6. **judge_should_continue**

   * 根据：

     * `iteration`（迭代次数）
     * `fetch_budget`（抓取预算）
     * `timeline.open_questions` 数量
   * 判断是：

     * 继续下一轮（回到 comment_triage）
     * 还是停止（进入 reporter）

7. **reporter**

   * 输入：最终 Timeline + Evidence
   * 生成：

     * 结构化事件报告（Markdown/文本形式）
     * 列出关键节点与证据对照关系

---

### 4. 对外接口形式（当前阶段）

MVP 阶段，只提供 **命令行接口（CLI）**：

* 示例调用：

  ```bash
  python -m src.interface.cli \
    --query "请梳理最近一个月小红书上关于 XXX 的翻车事件，起因经过结果是怎样的？"
  ```

* 行为：

  * 构建 GraphState
  * 运行 LangGraph StateGraph
  * 在终端输出简要事件链与报告摘要
  * 将完整报告保存为本地 Markdown 文件（例如：`reports/<timestamp>.md`）

后续可以在 `interface/web_app.py` 中添加：

* HTTP API（FastAPI）
* 简单 Web UI（查看时间线与报告），但不在本阶段范围内。
