"""
Retrieval Planner Agent: 分析时间线和疑点，规划下一步检索。
"""
from typing import List
from langchain_core.prompts import ChatPromptTemplate

from ..core.models.evidence import Evidence
from ..core.models.timeline import Timeline
from ..core.models.plan import RetrievalPlan, SearchQuery
from ..config.settings import settings
from ..llm.factory import init_llm


RETRIEVAL_PLANNER_SYSTEM_PROMPT = """你是一个专业的调查记者助手，负责规划下一步的信息检索策略。
你的任务是分析当前已有的事件时间线（Timeline）和待解决的疑点（Open Questions），判断是否需要进一步搜索信息。

如果需要进一步搜索，请生成具体的搜索查询（Search Queries），并说明理由。
如果当前信息已经足够清晰，或者没有明确的检索方向，请结束检索。

请遵循以下原则：
1. **聚焦疑点**：优先针对 Open Questions 中置信度低或关键信息缺失的部分生成查询。
2. **避免冗余**：不要重复搜索已经确定的信息。
3. **具体明确**：生成的查询语句应该是具体的关键词组合，适合搜索引擎使用。
4. **适度终止**：如果疑点过于模糊无法通过搜索解决，或者核心事件链已经完整，应选择结束。

请以 JSON 格式输出检索计划，包含以下字段：
- queries: 搜索查询对象列表。注意：列表中的每个元素必须是对象，包含 query 和 rationale 字段。
  - 正确示例: [{{\"query\": \"XXX精华 成分\", \"rationale\": \"查询成分表确认致敏源\"}}]
  - 错误示例: [\"XXX精华 成分\"]
- thought_process: 你的思考过程分析
- finish: 是否结束检索（true/false）
"""


async def plan_retrieval(timeline: Timeline, existing_evidences: List[Evidence]) -> RetrievalPlan:
    """规划检索策略。

    Args:
        timeline: 当前时间线（包含事件和疑点）
        existing_evidences: 已有的证据列表

    Returns:
        RetrievalPlan 实例（若出错则返回 finish=True 的空计划）
    """
    client = init_llm()

    # 收集 Open Questions 文本（如果有）
    open_questions_text = "无"
    if getattr(timeline, "open_questions", None):
        open_questions_text = "\n".join(
            [f"- [{q.id}] {q.question} (关联事件: {q.event_id or '全局'})" for q in timeline.open_questions]
        )

    # 简单的证据摘要（仅计数）
    evidence_summary = f"共 {len(existing_evidences)} 条证据。"

    # 组装完整的提示内容（直接放入系统提示中，避免变量占位）
    full_prompt = (
        RETRIEVAL_PLANNER_SYSTEM_PROMPT
        + "\n\nCurrent Timeline:\n"
        + timeline.to_markdown()
        + "\n\nOpen Questions:\n"
        + open_questions_text
        + "\n\nExisting Evidence Summary:\n"
        + evidence_summary
        + "\n\n请根据以上信息，规划下一步检索策略。"
    )

    # 使用仅系统消息的 PromptTemplate
    prompt = ChatPromptTemplate.from_messages([("system", full_prompt)])

    try:
        # 尝试结构化输出
        structured_llm = client.with_structured_output(RetrievalPlan)
        chain = prompt | structured_llm
        result = await chain.ainvoke({})
        return result
    except Exception as e:
        # 如果结构化输出失败，尝试获取原始文本并手动解析 JSON
        error_msg = str(e)
        print(f"[WARN] Structured output failed: {error_msg[:200]}")
        
        # 检查是否是 queries 格式问题（字符串而非对象）
        if "Input should be an object" in error_msg and "queries" in error_msg:
            print("[INFO] Detected string-based queries, attempting to fix...")
            try:
                # 尝试直接调用 LLM 获取原始 JSON
                raw_chain = prompt | client
                raw_result = await raw_chain.ainvoke({})
                import json
                content = raw_result.content if hasattr(raw_result, 'content') else str(raw_result)
                data = json.loads(content)
                
                # 处理 queries：如果是字符串列表，转换为对象列表
                queries = data.get("queries", [])
                if queries and isinstance(queries[0], str):
                    # LLM 返回了字符串列表，转换为 SearchQuery 对象
                    queries = [
                        SearchQuery(
                            query=q,
                            rationale="自动生成（LLM 返回格式不符）",
                            target_source=None,
                            related_open_question_id=None
                        ) for q in queries
                    ]
                
                return RetrievalPlan(
                    queries=queries,
                    thought_process=data.get("thought_process", ""),
                    finish=data.get("finish", True),
                )
            except Exception as e2:
                print(f"[ERROR] Fallback parsing also failed: {e2}")
                import traceback
                traceback.print_exc()
        
        # 最终保守策略：返回空计划并结束检索
        return RetrievalPlan(queries=[], thought_process=f"Planning failed: {error_msg[:100]}", finish=True)
