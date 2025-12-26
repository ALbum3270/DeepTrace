"""
Report Writer Agent: 基于时间线和证据生成叙事性调查报告。
"""
from typing import List, Set
import re
import logging
from datetime import datetime
from ..core.models.timeline import Timeline
from ..core.models.evidence import Evidence
from ..core.models.claim import Claim
from ..llm.factory import init_llm
from .prompts import REPORT_WRITER_SYSTEM_PROMPT
from langchain_core.prompts import ChatPromptTemplate
from ..infrastructure.utils.verification import verify_report

logger = logging.getLogger(__name__)


def sanitize_report_links(report_content: str, evidences: List[Evidence]) -> str:
    """
    Hard-coded Verification: 
    扫描报告中的 Markdown 链接，如果 URL 不在原始 Evidence 列表中，
    则强制移除该链接（只保留文本），防止 LLM 编造假 URL。
    """
    if not report_content:
        return report_content
    
    # 快速检查：如果没有 Markdown 链接格式，直接返回
    if '[' not in report_content or '](' not in report_content:
        return report_content

    # 1. 构建白名单
    valid_urls: Set[str] = set()
    for ev in evidences:
        if ev.url:
            url = str(ev.url).strip()
            valid_urls.add(url)
            valid_urls.add(url.rstrip('/'))  # 同时添加无斜杠版本
    
    # 2. 更鲁棒的正则：非贪婪匹配
    pattern = r'\[([^\]]*?)\]\(([^)]+?)\)'
    
    fake_links_removed = 0
    
    def replace_link(match):
        nonlocal fake_links_removed
        text = match.group(1)
        url = match.group(2).strip()
        
        # 归一化检查
        normalized_url = url.rstrip('/')
        is_valid = url in valid_urls or normalized_url in valid_urls
                
        if is_valid:
            return match.group(0)  # 保留原样
        else:
            fake_links_removed += 1
            logger.warning(f"Removed unverified link: {url[:50]}...")
            return f"{text} (⚠️ 链接未验证)"

    try:
        sanitized_content = re.sub(pattern, replace_link, report_content)
        if fake_links_removed > 0:
            logger.info(f"Link Sanitizer: removed {fake_links_removed} unverified links")
        return sanitized_content
    except Exception as e:
        logger.error(f"Link Sanitizer error: {e}")
        return report_content


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
    client = init_llm(timeout=300, enable_thinking=True)
    
    # 准备输入数据
    # Phase 18: Advanced Report Structuring
    
    # 1. Split Events
    main_timeline_events = []
    history_events = []
    rumor_events = []
    
    current_year_int = datetime.now().year
    current_year = str(current_year_int)
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    for ev in timeline.events:
        # Determine category
        # A. History: Happened before 2024 (or specific old models like GPT-4 launch)
        if ev.time and ev.time.year < 2024 and getattr(ev, 'model_family', '') == 'gpt-4-family':
            history_events.append(ev)
            continue
            
        # B. Rumors: Marked as rumor or opinion
        ev_type = getattr(ev, 'evidence_type', 'media')
        if ev_type in ('rumor', 'opinion'):
            rumor_events.append(ev)
            continue
            
        # C. Main Timeline: Official/Media and recent/future
        main_timeline_events.append(ev)

    def format_event_list(events):
        return "\n\n".join([
            f"### {ev.title}\n"
            f"- 时间: {ev.time.strftime('%Y-%m-%d') if ev.time else getattr(ev, 'date_precision', '未知')}\n"
            f"- 来源: {ev.source or '未知'} ({getattr(ev, 'evidence_type', 'media')})\n"
            f"- 阶段: {getattr(ev, 'phase', 'unknown')}\n"
            f"- 描述: {ev.description}\n"
            f"- 置信度: {ev.confidence:.2f}"
            for ev in events
        ])

    main_timeline_text = format_event_list(main_timeline_events) if main_timeline_events else "暂无核心事件"
    history_text = format_event_list(history_events) if history_events else "无相关历史背景"
    rumor_text = format_event_list(rumor_events) if rumor_events else "无相关传闻"

    # Claims 事实核查数据
    claims_text = "\n".join([
        f"- [{c.truth_status.value if hasattr(c, 'truth_status') else c.status}] {c.content} (可信度: {c.credibility_score:.0f}%)"
        for c in claims[:20]  # 最多显示 20 条
    ]) if claims else "暂无核查数据"
    
    # Open Questions
    open_questions = "\n".join([
        f"- [优先级 {q.priority:.2f}] {q.question}"
        for q in timeline.open_questions[:10]
    ]) if timeline.open_questions else "暂无待解疑点"
    
    # Future work (remaining tasks)
    future_work_text = "\n".join([
        f"- {task}" for task in remaining_tasks[:5]
    ]) if remaining_tasks else "暂无建议"
    
    # Evidence content preview
    evidences_content = "\n".join([
        f"- [{i+1}] ({e.source.value}) {e.title or '无标题'}: {e.content[:200]}..."
        for i, e in enumerate(evidences[:30])
    ]) if evidences else "暂无证据"
    
    # 组合 user message
    user_message_content = f"""# 重要规则
**当前日期**: {current_date}
**时间锚定**: 所有事件描述中的年份必须与证据中的实际时间一致。如果证据来自{current_year}年，请使用{current_year}年。请特别注意区分 2024 年和 2025 年的事件。

## ⚠️ 严禁捏造与过度推断规则（最高优先级）

1.  **用户引用与舆论**：
    -   **禁止**编造具体的 Reddit/Twitter/微博 用户名（如 `@devopsbear`）或直接引语。
    -   **必须**使用概括性表述，如“社区普遍认为...”、“有开发者反馈...”。
    -   除非你有 `canonical_text` 中明确的原文引用，否则不要使用引号。

2.  **因果关系推断**：
    -   **禁止**将并行的事件直接写成确定性的因果关系（例如：不要写“微软挖人**导致**了项目延期”）。
    -   **必须**使用“推测”、“可能相关”、“背景因素”等谨慎措辞，并标注为 [中置信度推测]。

3.  **官方命名与状态**：
    -   **必须**使用证据中出现的官方名称（如正式发布的产品名），而非民间俗称，除非你在文中专门做了解释。
    -   **必须**准确描述功能状态（如“实验性”、“预览版”），不要将“未来计划”写成“当前已上线”，也不要将“已上线”写成“仅限内部测试”（需检查最新证据时间）。

4.  **数据与规模**：
    -   **禁止**编造具体数字（如“数十亿次请求”、“89%正确率”），除非证据里有。
    -   **建议**使用模糊量词（如“大规模”、“广泛覆盖”）来替代缺乏证据的具体量级。

5.  **原文引用**：
    -   每个事实声明后面如果有 `原文引用`，请优先展示该原文。

# 调查话题
{topic}

# 1. 核心事件时间线（Main Timeline）
> 包含已确认的官方公告和权威媒体报道 (Official/Media)。
{main_timeline_text}

# 2. 历史背景 (History & Context)
> 包含前代模型或去年的相关背景事件。
{history_text}

# 3. 争议与传闻 (Rumors & Controversy)
> 包含爆料、未证实传闻及媒体观点 (Rumor/Opinion)。
{rumor_text}

# 4. 事实核查数据 (Claims Fact Check)
{claims_text}

# 5. 待解疑点 (Open Questions & Conflicts)
{open_questions}

# 6. 建议进一步调查的方向
{future_work_text}

# 7. 证据内容预览（共 {len(evidences)} 条，仅展示前30条）
{evidences_content}

请基于以上结构化信息，撰写一篇连贯、深入的调查报告。
**结构要求**：
1. **Executive Summary**: 仅基于 Main Timeline 和 Verified Claims 撰写。
2. **Main Body**: 按逻辑讲述核心事件。
3. **Rumor Mill**: 单独一个章节讨论 "争议与传闻"，明确指出这些信息未证实。
4. **Conclusion**: 总结。
严格遵守上述“严禁捏造与过度推断规则”。"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", REPORT_WRITER_SYSTEM_PROMPT),
        ("user", "{input}")
    ])
    
    try:
        chain = prompt | client
        
        # 使用流式输出以避免超时并支持长文本
        logger.info("Starting streamed report generation...")
        full_content = ""
        
        async for chunk in chain.astream({"input": user_message_content}):
            if hasattr(chunk, 'content') and chunk.content:
                full_content += chunk.content
        
        final_content = full_content
            
        # --- 统一验证层: verify_report ---
        final_content, verification_stats = verify_report(final_content, evidences, claims)
        logger.info(f"Verification stats: {verification_stats}")
        # -----------------------------------
        
        return final_content
            
    except Exception as e:
        error_str = str(e)
        logger.error(f"Narrative report generation failed: {error_str}")
        
        # 通用回退逻辑：无论何种错误（API失败、内容拦截、网络错误），都生成结构化报告
        logger.warning(f"Generating structured fallback report. Reason: {error_str}")
        
        # 生成事件摘要
        events_summary = "\n".join([
            f"- **{ev.title}** ({ev.time.strftime('%Y-%m-%d') if ev.time else '未知时间'}): {ev.description[:150]}..."
            for ev in timeline.events[:15]
        ]) if timeline.events else "暂无事件数据"
        
        claims_summary = claims_text  # 使用已定义的 claims_text
        
        # 错误类型判断
        error_type = "生成服务不可用"
        error_hint = f"由于技术原因 ({error_str[:50]}...)，智能叙事无法生成。"
        if "data_inspection_failed" in error_str or "inappropriate content" in error_str:
            error_type = "内容安全拦截"
            error_hint = "由于话题涉及敏感内容，智能叙事生成已被拦截。"
            
        fallback_report = f"""# 调查报告（{error_type}）

> ⚠️ **注意**: {error_hint} 以下为您展示基于原始数据的结构化事实清单。

## 1. 核心事实梳理

{events_summary}

## 2. 事实核查数据

{claims_summary}

## 3. 关键证据列表（前10条）

"""
        # 添加前 10 条证据的详细信息
        for i, ev in enumerate(evidences[:10]):
            ev_content_preview = ev.content[:300].replace('\n', ' ') if ev.content else "无内容"
            fallback_report += f"""### 证据 {i+1}: {ev.title or '无标题'}
- **来源**: {ev.source.value if hasattr(ev.source, 'value') else str(ev.source)}
- **链接**: {ev.url or '无'}
- **内容预览**: {ev_content_preview}{'...' if len(ev.content or '') > 300 else ''}

"""
        return fallback_report
