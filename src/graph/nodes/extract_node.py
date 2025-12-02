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
    
    # Layer 1 Deduplication: Evidence Level
    unique_evidences = []
    seen_urls = set()
    seen_titles = {} # title -> platform

    for ev in evidences:
        if not ev.url:
            unique_evidences.append(ev)
            continue
            
        if ev.url in seen_urls:
            continue
        seen_urls.add(ev.url)
        
        # Title check for cross-platform reposts
        if ev.title:
            if ev.title in seen_titles:
                existing_platform = seen_titles[ev.title]
                current_platform = ev.metadata.get("platform", "unknown")
                if existing_platform != current_platform:
                    # Mark as cross-platform repost
                    ev.metadata["is_repost"] = True
                    ev.metadata["repost_source_platform"] = existing_platform
                    # We still keep it to extract platform-specific reactions, 
                    # but downstream event dedup will handle the merge.
            else:
                seen_titles[ev.title] = ev.metadata.get("platform", "unknown")
            
        unique_evidences.append(ev)

    if len(evidences) != len(unique_evidences):
        print(f"[Extract] Deduplicated evidences: {len(evidences)} -> {len(unique_evidences)}")

    # 并发处理所有 Evidence 提取事件
    tasks = [extract_event_from_evidence(ev) for ev in unique_evidences]
    results = await asyncio.gather(*tasks)
    
    # 过滤掉 None 的事件
    events = [e for e in results if e]
            
    return {
        "events": events,
        "steps": [f"extract_events: got {len(events)} events"]
    }

async def extract_comments_node(state: GraphState) -> GraphState:
    """
    Extract Comments Node: 从证据中提取评论（支持 HTML 内容和深度全文挖掘）。
    Reads: state.evidences
    Writes: state.comments
    """
    evidences = state.get("evidences", [])
    
    if not evidences:
        return {
            "steps": ["extract_comments: no evidences, skip"]
        }
        
    # 并发处理所有 Evidence 提取评论
    # extract_comments_from_article 内部会自动优先使用 full_content
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
        "steps": [f"extract_comments: extracted {len(all_comments)} comments"]
    }
