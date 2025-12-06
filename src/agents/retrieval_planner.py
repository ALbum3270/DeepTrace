
"""
Retrieval Planner Agent: 分析时间线和疑点，规划下一步检索。
"""
import json
from typing import List, Set
from langchain_core.prompts import ChatPromptTemplate

from ..core.models.evidence import Evidence
from ..core.models.timeline import Timeline
from ..core.models.plan import RetrievalPlan, SearchQuery
from ..config.settings import settings
from ..llm.factory import init_llm


RETRIEVAL_PLANNER_SYSTEM_PROMPT = """你是一个专业的调查记者助手，负责规划下一步的信息检索策略。
你的任务是分析当前已有的事件时间线（Timeline）和待解决的疑点（Open Questions），判断是否需要进一步搜索信息。

特别注意：利用 'Comment Insights'（评论洞察）中的线索（如新出现的实体、观点冲突）来进行“顺藤摸瓜”式的二次检索。

请遵循以下原则：
1. **聚焦疑点**：优先针对 Open Questions 中置信度低或关键信息缺失的部分生成查询。
2. **挖掘评论**：关注 Evidence 中提取的 'comment_insights'，寻找新的搜索方向。
3. **避免冗余**：不要重复搜索已经确定的信息。
4. **具体明确**：生成的查询语句应该是具体的关键词组合。
5. **适度终止**：如果疑点过于模糊无法通过搜索解决，或者核心事件链已经完整，应选择结束。

请以 JSON 格式输出检索计划，包含以下字段：
- queries: 搜索查询对象列表。注意：列表中的每个元素必须是对象，包含 query 和 rationale 字段。
- thought_process: 你的思考过程分析
- finish: 是否结束检索（true/false）
"""


async def plan_retrieval(timeline: Timeline, existing_evidences: List[Evidence], seen_queries: Set[str] = None) -> RetrievalPlan:
    """规划检索策略。

    Args:
        timeline: 当前时间线（包含事件和疑点）
        existing_evidences: 已有的证据列表
        seen_queries: 已执行过的查询集合（用于防环）

    Returns:
        RetrievalPlan 实例
    """
    client = init_llm()
    seen_queries = seen_queries or set()

    # 收集 Open Questions 文本
    open_questions_text = "无"
    if getattr(timeline, "open_questions", None):
        open_questions_text = "\n".join(
            [f"- [{q.id}] {q.question} (关联事件: {q.related_event_ids or '全局'})" for q in timeline.open_questions]
        )

    # 构造 Evidence Context (包含 Comment Insights)
    # 取最近的 5 条证据，避免 Context 过长
    recent_evidences = existing_evidences[-5:] if existing_evidences else []
    evidence_context_list = []
    for ev in recent_evidences:
        context = f"Title: {ev.title}\nURL: {ev.url}"
        insights = ev.metadata.get("comment_insights")
        if insights:
            # 简化 Insight 展示
            clusters = insights.get("top_opinion_clusters", [])
            cluster_summary = "; ".join([f"{c.get('summary')} (Size:{c.get('size')})" for c in clusters[:3]])
            entities = ", ".join(insights.get("new_entities", [])[:5])
            context += f"\nComment Insights:\n  - Opinions: {cluster_summary}\n  - Entities: {entities}"
        evidence_context_list.append(context)
    
    evidence_summary = "\n---\n".join(evidence_context_list) or "暂无证据"

    # 组装完整的提示内容
    full_prompt = (
        RETRIEVAL_PLANNER_SYSTEM_PROMPT
        + "\n\nCurrent Timeline:\n"
        + timeline.to_markdown()
        + "\n\nOpen Questions:\n"
        + open_questions_text
        + "\n\nRecent Evidence & Insights:\n"
        + evidence_summary
        + "\n\n请根据以上信息，规划下一步检索策略。"
    )

    # 使用仅系统消息的 PromptTemplate
    prompt = ChatPromptTemplate.from_messages([("system", "{input}")])

    try:
        # 尝试结构化输出
        structured_llm = client.with_structured_output(RetrievalPlan)
        chain = prompt | structured_llm
        result = await chain.ainvoke({"input": full_prompt})
        
        # --- Recursion Safety & Limits ---
        valid_queries = []
        for q in result.queries:
            # Normalize: strip whitespace, lowercase
            norm_q = q.query.strip().lower()
            if norm_q not in seen_queries:
                valid_queries.append(q)
                # Note: We don't add to seen_queries here, caller handles state update
            else:
                print(f"[Planner] Filtered duplicate query: {q.query}")
        
        # Enforce Max New Queries Limit
        if len(valid_queries) > settings.MAX_NEW_QUERIES_PER_ROUND:
            print(f"[Planner] Capping queries from {len(valid_queries)} to {settings.MAX_NEW_QUERIES_PER_ROUND}")
            valid_queries = valid_queries[:settings.MAX_NEW_QUERIES_PER_ROUND]
            
        result.queries = valid_queries
        
        if not valid_queries and not result.finish:
             # If all queries were filtered but LLM wanted to continue, force finish or log warning
             # For now, we let it return empty queries, loop logic will handle it (no new queries -> stop or retry)
             pass

        return result
        
    except Exception as e:
        # Fallback logic (simplified for brevity, keeping original error handling structure if needed)
        print(f"[WARN] Planner failed: {e}")
        return RetrievalPlan(queries=[], thought_process=f"Planning failed: {e}", finish=True)

