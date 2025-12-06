"""
Report Writer Agent: 基于时间线和证据生成叙事性调查报告。
"""
from typing import List
from ..core.models.timeline import Timeline
from ..core.models.evidence import Evidence
from ..core.models.claim import Claim
from ..llm.factory import init_llm
from .prompts import REPORT_WRITER_SYSTEM_PROMPT
from langchain_core.prompts import ChatPromptTemplate


async def write_narrative_report(
    topic: str,
    timeline: Timeline,
    evidences: List[Evidence],
    claims: List[Claim] = [],
    remaining_tasks: List[str] = []
) -> str:
    """
    生成叙事性调查报告。
    
    Args:
        topic: 调查话题
        timeline: 事件时间线
        evidences: 所有证据列表
        
    Returns:
        Markdown 格式的报告文本
    """
    client = init_llm(timeout=300)
    
    # 准备输入数据
    events_summary = "\n\n".join([
        f"### {ev.title}\n"
        f"- 时间: {ev.time.strftime('%Y-%m-%d %H:%M') if ev.time else '未知'}\n"
        f"- 来源: {ev.source or '未知'}\n"
        f"- 描述: {ev.description}\n"
        f"- 置信度: {ev.confidence:.2f}"
        for ev in timeline.events
    ])
    
    evidences_content = "\n\n---\n\n".join([
        f"**证据 {i+1}** ({ev.source.value if hasattr(ev.source, 'value') else str(ev.source)})\n"
        f"来源: {ev.title or '无标题'}\n"
        f"URL: {ev.url or '无'}\n"
        f"内容:\n{ev.content[:2000]}{'...' if len(ev.content) > 2000 else ''}"
        for i, ev in enumerate(evidences[:30])  # Optimized Limit: 30 evidences to prevent timeout
    ])
    
    open_questions = "\n".join([
        f"- {q.question}"
        for q in timeline.open_questions
    ]) if timeline.open_questions else "无"
    
    # 构造 Claims 信息
    claims_text = ""
    if claims:
        # 分类
        verified = [c for c in claims if c.status == "verified" or (c.credibility_score >= 80 and c.status != "disputed")]
        disputed = [c for c in claims if c.status == "disputed" or (c.status == "unverified" and c.importance > 60)]
        
        claims_text += "# 核心事实核查 (Claims Analysis)\n"
        if verified:
            claims_text += "## 已验证/高置信度事实\n" + "\n".join([f"- {c.content} (可信度: {c.credibility_score})" for c in verified]) + "\n\n"
        if disputed:
            claims_text += "## 争议/待验证声明\n" + "\n".join([f"- {c.content} (来源可信度: {c.credibility_score})" for c in disputed]) + "\n\n"

    # Future Tasks
    future_work_text = ""
    if remaining_tasks:
        future_work_text = "# 建议进一步调查的方向 (Unexplored)\n" + "\n".join([f"- {task}" for task in remaining_tasks])
    
    # 组合 user message
    user_message_content = f"""# 调查话题
{topic}

# 事件时间线（{len(timeline.events)} 个事件）
{events_summary}

# 事实核查数据
{claims_text}

# 待解疑点
{open_questions}


# 建议进一步调查的方向
{future_work_text}

# 证据内容（共 {len(evidences)} 条，仅展示前30条核心证据）
{evidences_content}

请基于以上信息，撰写一篇连贯、深入的调查报告。如果存在"建议进一步调查的方向"，请在报告末尾的"结论与未解疑点"部分提及。"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", REPORT_WRITER_SYSTEM_PROMPT),
        ("user", "{input}")
    ])
    
    try:
        chain = prompt | client
        result = await chain.ainvoke({"input": user_message_content})
        
        # 提取文本内容
        if hasattr(result, 'content'):
            return result.content
        else:
            return str(result)
            
    except Exception as e:
        error_str = str(e)
        print(f"[ERROR] Narrative report generation failed: {error_str}")
        
        # Fallback for Content Safety Errors (Aliyun/OpenAI)
        if "data_inspection_failed" in error_str or "inappropriate content" in error_str:
            print("[WARN] Content safety filter triggered. Generating fallback report.")
            fallback_report = f"""# 调查报告（安全模式）
            
> ⚠️ **注意**: 由于话题涉及敏感内容，智能叙事生成已被拦截。以下为您展示基于原始数据的结构化事实清单。

## 1. 核心事实梳理

{events_summary}

## 2. 关键证据列表

"""
            # Add simple evidence list
            for i, ev in enumerate(evidences[:20]):
                fallback_report += f"- **[{i+1}] {ev.title or '无标题'}**\n  - 来源: {ev.source}\n  - 链接: {ev.url}\n"
                
            return fallback_report
            
        return f"# 报告生成失败\n\n错误信息: {error_str}\n\n请查看结构化报告 (report.md) 了解详情。"
