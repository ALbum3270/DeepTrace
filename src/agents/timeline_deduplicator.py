from typing import List, Set
from datetime import datetime
from difflib import SequenceMatcher
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from ..core.models.events import EventNode
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
        3. **细节互补**：即使描述侧重点不同，只要核心事实重叠，也视为同一事件。
        
        请输出 JSON：{{"is_duplicate": true/false, "reason": "..."}}
        """),
        ("user", """
        事件 A:
        时间: {time1}
        标题: {title1}
        描述: {desc1}
        
        事件 B:
        时间: {time2}
        标题: {title2}
        描述: {desc2}
        """)
    ])
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "time1": event1.time, "title1": event1.title, "desc1": event1.description,
            "time2": event2.time, "title2": event2.title, "desc2": event2.description
        })
        return result.get("is_duplicate", False)
    except Exception as e:
        print(f"[WARN] Deduplication LLM check failed: {e}")
        return False

async def deduplicate_events(events: List[EventNode]) -> List[EventNode]:
    """
    对事件列表进行语义去重。
    策略：
    1. 按时间排序。
    2. 两两比较：
       - Level 1: 标题相似度 > 0.6 -> 进入 Level 2
       - Level 2: LLM 判断是否重复
    3. 合并重复事件。
    """
    if not events:
        return []
        
    # 按时间排序
    # 按时间排序 (None 视为最早)
    sorted_events = sorted(events, key=lambda x: x.time or datetime.min)
    merged_events: List[EventNode] = []
    
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
            
            # Level 1: 快速筛选 (标题相似度)
            # 如果标题为空，尝试用描述的前50个字符
            text1 = current_event.title or current_event.description[:50]
            text2 = candidate.title or candidate.description[:50]
            
            similarity = calculate_similarity(text1, text2)
            
            # Debug print
            print(f"[Dedup] Comparing '{text1}' vs '{text2}' -> Similarity: {similarity:.4f}")
            
            is_duplicate = False
            if similarity > 0.85:
                # 极高相似度，直接认定重复
                is_duplicate = True
                print(f"[Dedup] Auto-merge (High Similarity): {similarity:.4f}")
            elif similarity > 0.6:
                # 中等相似度，调用 LLM 确认 (Level 2)
                print(f"[Dedup] Checking LLM for '{text1}' vs '{text2}' (Sim: {similarity:.4f})")
                is_duplicate = await are_events_duplicate_llm(current_event, candidate)
            
            if is_duplicate:
                print(f"[Dedup] Merging: {candidate.title} -> {current_event.title}")
                # 合并逻辑
                # 1. 保留更长的描述
                if len(candidate.description or "") > len(current_event.description or ""):
                    current_event.description = candidate.description
                    current_event.title = candidate.title # 同时也更新标题
                
                # 2. 合并证据 ID
                current_event.evidence_ids = list(set(current_event.evidence_ids + candidate.evidence_ids))
                
                # 3. 取最大置信度
                current_event.confidence = max(current_event.confidence, candidate.confidence)
                
                # 标记 candidate 为已处理
                skip_indices.add(j)
                # print(f"[Dedup] Merged event: {candidate.title} -> {current_event.title}")
        
        merged_events.append(current_event)
        
    return merged_events
