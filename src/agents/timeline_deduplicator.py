from typing import List, Set, Tuple
from datetime import datetime
from difflib import SequenceMatcher
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from ..core.models.events import EventNode, OpenQuestion
from ..llm.factory import init_llm

class DeduplicationResult(BaseModel):
    is_duplicate: bool = Field(..., description="是否为重复事件")
    reason: str = Field(..., description="判断理由")

def calculate_similarity(text1: str, text2: str) -> float:
    """计算两个文本的相似度 (0.0 - 1.0)"""
    return SequenceMatcher(None, text1, text2).ratio()

async def are_events_duplicate_llm(event1: EventNode, event2: EventNode) -> bool:
    """使用 LLM 判断两个事件是否描述同一件事"""
    llm = init_llm()
    parser = JsonOutputParser(pydantic_object=DeduplicationResult)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个事件去重专家。请判断以下两个事件是否描述的是同一个具体事件。
        
        判断标准：
        1. **核心事实一致**：主体、动作、结果基本相同。
        2. **时间相近**：发生时间非常接近（允许有少量误差）。
        3. **跨平台兼容**：即使一个是新闻报道（侧重事实），一个是社交媒体评论（侧重观点），只要它们讨论的是同一个具体事件节点，也视为同一事件。
        
        请输出 JSON：{{"is_duplicate": true/false, "reason": "..."}}
        """),
        ("user", "{input}")
    ])
    
    chain = prompt | llm | parser
    
    try:
        user_content = f"""
        事件 A:
        时间: {event1.time}
        标题: {event1.title}
        描述: {event1.description}
        
        事件 B:
        时间: {event2.time}
        标题: {event2.title}
        描述: {event2.description}
        """
        result = await chain.ainvoke({"input": user_content})
        return result.get("is_duplicate", False)
    except Exception as e:
        print(f"[WARN] Deduplication LLM check failed: {e}")
        return False

def get_source_priority(source: str) -> int:
    """Determine source priority: News (2) > Social (1) > Unknown (0)"""
    source = (source or "").lower()
    if any(k in source for k in ["news", "report", "sina", "qq", "daily", "times", "新闻", "网", "报"]):
        return 2
    if any(k in source for k in ["weibo", "xhs", "xiaohongshu", "twitter", "facebook", "微博", "小红书"]):
        return 1
    return 0

def merge_event_content(target: EventNode, source: EventNode):
    """Merge source event into target event with priority logic."""
    p_target = get_source_priority(target.source)
    p_source = get_source_priority(source.source)
    
    # Determine Base (High Priority) and Supplement (Low Priority)
    if p_source > p_target:
        base, supplement = source, target
    else:
        base, supplement = target, source
        
    # 1. Title & Source: Always use Base
    target.title = base.title
    target.source = base.source
    
    # 2. Description Fusion
    # If different types (News vs Social), append Social as perspective
    if p_target != p_source and abs(p_target - p_source) > 0:
        # Check if supplement description is already contained? 
        # For now, just append as perspective.
        target.description = f"{base.description}\n\n【补充视角】({supplement.source or '其他'}): {supplement.description}"
    else:
        # Same type: keep the longer/richer description
        if len(supplement.description or "") > len(base.description or ""):
            target.description = supplement.description
        else:
            target.description = base.description

    # 3. Merge Evidences & Confidence
    target.evidence_ids = list(set(target.evidence_ids + source.evidence_ids))
    target.confidence = max(target.confidence, source.confidence)

async def rewrite_and_merge_event(target: EventNode, source: EventNode):
    """
    Use LLM to rewrite the target event description by fusing content from source.
    """
    # 1. Determine Base vs Supplement logic first (to set title/source correctly)
    p_target = get_source_priority(target.source)
    p_source = get_source_priority(source.source)
    
    if p_source > p_target:
        base, supplement = source, target
    else:
        base, supplement = target, source
        
    # Update metadata first
    target.title = base.title
    target.source = base.source
    target.evidence_ids = list(set(target.evidence_ids + source.evidence_ids))
    target.confidence = max(target.confidence, source.confidence)
    
    # 2. Call LLM for Description Rewrite
    llm = init_llm()
    from langchain_core.output_parsers import StrOutputParser
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert editor. Combine the following two event descriptions into a single, cohesive narrative.
        
        **Instructions**:
        1. Keep the core facts from the Base description.
        2. Integrate the Supplement as a "Community Perspective" or "Additional Context" section, but make it flow naturally.
        3. Do NOT simply append. Synthesize.
        4. Output ONLY the new description text.
        """),
        ("user", "{input}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        user_content = f"""
        - **Base (Fact-focused)**: {base.description}
        - **Supplement (Perspective-focused)**: {supplement.description}
        
        Rewrite now.
        """
        new_desc = await chain.ainvoke({"input": user_content})
        target.description = new_desc
    except Exception as e:
        print(f"[WARN] Fusion rewrite failed: {e}. Fallback to append.")
        # Fallback
        target.description = f"{base.description}\n\n【补充视角】({supplement.source or '其他'}): {supplement.description}"


async def deduplicate_events(events: List[EventNode]) -> Tuple[List[EventNode], List[OpenQuestion]]:
    """
    对事件列表进行语义去重 (Layer 2)。
    策略：
    1. 按时间排序。
    2. 两两比较：
       - Filter: 时间窗口 (2天) & 标题相似度 (>0.6)
       - Check: LLM 判断是否为同一具体事件
    3. 合并: News为主，Social为辅。
    4. 冲突检测: 若合并事件时间差异过大，生成 OpenQuestion。
    """
    if not events:
        return [], []
        
    # 按时间排序 (None 视为最早)
    sorted_events = sorted(events, key=lambda x: x.time or datetime.min)
    merged_events: List[EventNode] = []
    open_questions: List[OpenQuestion] = []
    
    skip_indices: Set[int] = set()
    
    for i in range(len(sorted_events)):
        if i in skip_indices:
            continue
            
        current_event = sorted_events[i]
        
        # 向后寻找重复项
        for j in range(i + 1, len(sorted_events)):
            if j in skip_indices:
                continue
                
            candidate = sorted_events[j]
            
            # 0. Time Window Filter (2 days)
            if current_event.time and candidate.time:
                delta = abs((current_event.time - candidate.time).days)
                if delta > 2:
                    continue # Skip if too far apart
            
            # 1. Cheap Similarity Filter
            text1 = current_event.title or current_event.description[:50]
            text2 = candidate.title or candidate.description[:50]
            similarity = calculate_similarity(text1, text2)
            
            is_duplicate = False
            
            if similarity > 0.85:
                # 极高相似度，直接认定重复
                is_duplicate = True
                print(f"[Dedup] Auto-merge (High Sim {similarity:.2f}): '{text1}' vs '{text2}'")
            elif similarity > 0.6:
                # 中等相似度，调用 LLM 确认
                print(f"[Dedup] Checking LLM (Sim {similarity:.2f}): '{text1}' vs '{text2}'")
                is_duplicate = await are_events_duplicate_llm(current_event, candidate)
            
            if is_duplicate:
                print(f"[Dedup] Merging: {candidate.title} -> {current_event.title}")
                
                # Conflict Check (Date mismatch > 1 day, stricter for merged events)
                if current_event.time and candidate.time:
                    delta = abs((current_event.time - candidate.time).days)
                    if delta > 1:
                        q = OpenQuestion(
                            question=f"关于事件 '{current_event.title}' 的发生时间存在争议。",
                            context=f"来源 '{current_event.source}' 称时间为 {current_event.time}，而来源 '{candidate.source}' 称时间为 {candidate.time}。",
                            related_event_ids=[current_event.id, candidate.id],
                            priority=0.8
                        )
                        open_questions.append(q)
                        print(f"[Dedup] Conflict detected: {q.question}")

                # Fusion Rewrite: Use LLM to merge descriptions if sources differ significantly
                # Check if we are merging News + Social
                p_current = get_source_priority(current_event.source)
                p_candidate = get_source_priority(candidate.source)
                
                if p_current != p_candidate and abs(p_current - p_candidate) > 0:
                     print(f"[Dedup] Cross-platform merge detected. Rewriting description...")
                     # We need to await this, so we can't use the sync merge_event_content easily
                     # Let's inline the logic or make a new async function
                     await rewrite_and_merge_event(current_event, candidate)
                else:
                     merge_event_content(current_event, candidate)
                     
                skip_indices.add(j)
        
        merged_events.append(current_event)
        
    return merged_events, open_questions
