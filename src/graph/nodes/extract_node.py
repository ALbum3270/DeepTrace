import asyncio
from typing import List
from ..state import GraphState
from ...agents.event_extractor import extract_event_from_evidence
from ...agents.comment_extractor import extract_comments_from_article
from ...core.models.events import EventNode
from ...core.models.comments import Comment

async def extract_events_node(state: GraphState) -> GraphState:
    """
    Extract Events Node: 仅从证据中提取事件。
    Reads: state.evidences
    Writes: state.events
    """
    evidences = state.get("evidences", [])
    
    if not evidences:
        return {
            "steps": ["extract_events: no evidences, skip"]
        }
    
    # 并发处理所有 Evidence 提取事件
    tasks = [extract_event_from_evidence(ev) for ev in evidences]
    results = await asyncio.gather(*tasks)
    
    # 过滤掉 None 的事件
    events = [e for e in results if e]
            
    return {
        "events": events,
        "steps": [f"extract_events: got {len(events)} events"]
    }

async def extract_comments_node(state: GraphState) -> GraphState:
    """
    Extract Comments Node: 仅从证据中提取评论。
    Reads: state.evidences
    Writes: state.comments
    """
    evidences = state.get("evidences", [])
    
    if not evidences:
        return {
            "steps": ["extract_comments: no evidences, skip"]
        }
        
    # 并发处理所有 Evidence 提取评论
    tasks = [extract_comments_from_article(ev) for ev in evidences]
    results = await asyncio.gather(*tasks)
    
    # Flatten list of lists
    all_comments: List[Comment] = []
    for comments in results:
        if comments:
            all_comments.extend(comments)
            
    if all_comments:
        print(f"[Extract] Extracted {len(all_comments)} comments total")
            
    return {
        "comments": all_comments,
        "steps": [f"extract_comments: got {len(all_comments)} comments"]
    }
