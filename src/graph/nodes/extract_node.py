import asyncio
from typing import List, Dict
from ..state import GraphState
from ...agents.event_extractor import extract_event_from_evidence
from ...agents.comment_extractor import extract_comments_from_article
from ...core.models.comments import Comment
from ...core.models.evidence import Evidence

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
    processed_ids = state.get("processed_evidence_ids") or set()
    new_processed_ids = set()

    for ev in evidences:
        if ev.id in processed_ids: # Incremental Check
            continue
            
        if not ev.url:
            unique_evidences.append(ev)
            new_processed_ids.add(ev.id)
            continue
            
        if ev.url in seen_urls:
            # Mark as processed because it's duplicate
            new_processed_ids.add(ev.id)
            continue
        seen_urls.add(ev.url)
        
        # Mark as processed
        new_processed_ids.add(ev.id)
        
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
    current_query = state.get("current_query", "")
    tasks = [extract_event_from_evidence(ev, query=current_query) for ev in unique_evidences]
    results = await asyncio.gather(*tasks)
    
    # 过滤掉 None 的事件和声明
    events = []
    claims = []
    
    for res in results:
        if not res:
            continue
        # extract_event_from_evidence returns (EventNode, List[Claim])
        event, ev_claims = res
        if event:
            events.append(event)
        if ev_claims:
            claims.extend(ev_claims)
            
    return {
        "events": events,
        "claims": claims,
        "processed_evidence_ids": processed_ids.union(new_processed_ids),
        "steps": [f"extract_events: got {len(events)} events, {len(claims)} claims from {len(unique_evidences)} new evidences"]
    }

from ...fetchers.weibo.client import WeiboClient
from ...core.models.plan import WeiboCommentDepth
from ...infrastructure.utils.time_util import rfc2822_to_china_datetime
import os
import re
from uuid import uuid4

def _resolve_limits(depth_config: WeiboCommentDepth) -> tuple[int, int]:
    """
    Resolve mode to (max_pages, max_comments).
    Hard limits are enforced here.
    """
    mode = depth_config.mode
    hint_limit = depth_config.suggested_max_comments
    
    if mode == "skip":
        return 0, 0
    elif mode == "shallow":
        return 1, 20
    elif mode == "deep":
        # Hard cap: 10 pages or 500 comments
        limit = min(hint_limit, 500) if hint_limit else 200
        return 10, limit
    else: # normal / auto
        limit = min(hint_limit, 100) if hint_limit else 50
        return 3, limit

async def _enrich_weibo_evidence(evidence: Evidence, depth_config: WeiboCommentDepth) -> List[Comment]:
    """
    Fetch comments from Weibo API and attach to evidence.
    """
    # Extract mid from URL or metadata
    mid = None
    if evidence.metadata.get("mblog", {}).get("id"):
        mid = str(evidence.metadata["mblog"]["id"])
    else:
        match = re.search(r'detail/(\d+)', evidence.url)
        if match:
            mid = match.group(1)
            
    if not mid:
        return []

    max_pages, max_comments = _resolve_limits(depth_config)
    if max_comments <= 0:
        return []
        
    # Re-initialize client with cookies from env
    cookie_str = os.getenv("DEEPTRACE_WEIBO_COOKIES", "")
    cookie_dict = {}
    if cookie_str:
        for item in cookie_str.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookie_dict[k] = v
    client = WeiboClient(cookie_dict=cookie_dict)
    
    try:
        raw_comments = await client.fetch_comments_api(mid, max_pages, max_comments)
    except Exception as e:
        print(f"[Extract] API fetch failed for {mid}: {e}")
        return []
    
    comments = []
    for raw in raw_comments:
        publish_time = None
        if raw.get("created_at"):
            try:
                publish_time = rfc2822_to_china_datetime(raw["created_at"])
            except Exception:
                pass
                
        c = Comment(
            id=str(uuid4()),
            content=raw.get("text", ""),
            author=raw.get("user", {}).get("screen_name", "Unknown"),
            role="public_opinion",
            source_evidence_id=evidence.id,
            source_url=evidence.url,
            publish_time=publish_time
        )
        comments.append(c)
        
    return comments

from ...llm.factory import init_json_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

async def _generate_comment_insights(comments: List[Comment]) -> Dict:
    """
    Generate insights from comments using LLM.
    """
    if not comments:
        return {}
        
    # Limit context window
    sample_comments = comments[:50]
    text_lines = [f"- {c.content}" for c in sample_comments]
    text = "\n".join(text_lines)
    
    system_prompt = """You are an expert analyst. Analyze the following social media comments and extract insights in JSON format.
    
    Output Structure:
    {{
        "top_opinion_clusters": [
            {{"summary": "Brief summary of the opinion", "size": "Estimated count in sample", "example_comments": ["quote 1", "quote 2"]}}
        ],
        "new_entities": ["Entity1", "Entity2"],
        "controversy_signals": {{
            "has_strong_disagreement": true/false,
            "has_fact_dispute": true/false
        }}
    }}
    """
    
    human_prompt = f"Comments:\n{text}"
    
    try:
        llm = init_json_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])
        chain = prompt | llm | JsonOutputParser()
        return await chain.ainvoke({})
    except Exception as e:
        print(f"[Extract] Insight generation failed: {e}")
        return {}

async def extract_comments_node(state: GraphState) -> GraphState:
    """
    Extract Comments Node: 从证据中提取评论（支持 HTML 内容和深度全文挖掘）。
    Reads: state.evidences
    Writes: state.comments
    """
    evidences = state.get("evidences", [])
    depth_config = state.get("weibo_comment_depth") or WeiboCommentDepth()
    
    if not evidences:
        return {
            "steps": ["extract_comments: no evidences, skip"]
        }
        
    all_comments: List[Comment] = []
    
    # Process evidences
    tasks = []
    for ev in evidences:
        # Check if it's a Weibo evidence
        is_weibo = (ev.url and "weibo" in ev.url) or ev.metadata.get("platform") == "weibo"
        
        if is_weibo and depth_config.mode != "skip":
            # Use API fetching for Weibo
            tasks.append(_enrich_weibo_evidence(ev, depth_config))
        else:
            # Fallback to LLM extraction from body
            tasks.append(extract_comments_from_article(ev))

    results = await asyncio.gather(*tasks)
    
    # Attach comments and generate insights
    insight_tasks = []
    for i, comments in enumerate(results):
        if comments:
            evidences[i].comments = comments # Attach to evidence
            all_comments.extend(comments)
            # Generate insights
            insight_tasks.append(_generate_comment_insights(comments))
        else:
            insight_tasks.append(asyncio.sleep(0)) # Placeholder
            
    # Wait for insights
    insights_results = await asyncio.gather(*insight_tasks)
    
    for i, insights in enumerate(insights_results):
        if insights and isinstance(insights, dict):
            evidences[i].metadata["comment_insights"] = insights
            
    if all_comments:
        print(f"[Extract] Extracted {len(all_comments)} comments total (Mode: {depth_config.mode})")
            
    return {
        "comments": all_comments,
        "steps": [f"extract_comments: extracted {len(all_comments)} comments (Mode: {depth_config.mode})"]
    }
