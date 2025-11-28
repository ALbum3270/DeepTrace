from typing import List
from ..state import GraphState
from ...agents.event_extractor import extract_event_from_evidence
from ...core.models.events import EventNode

async def extract_node(state: GraphState) -> GraphState:
    """
    Extract Node: 从证据中提取事件。
    """
    evidences = state.get("evidences", [])
    
    # 短路处理：如果没有证据，直接跳过
    if not evidences:
        return {
            "steps": ["extract: no evidences, skip"]
        }
    
    events: List[EventNode] = []
    
    # 遍历所有证据进行提取
    # TODO: 未来可以改为并发执行 (asyncio.gather)
    for ev in evidences:
        event = await extract_event_from_evidence(ev)
        if event:
            events.append(event)
            
    return {
        "events": events,
        "steps": [f"extract: got {len(events)} events from {len(evidences)} evidences"]
    }
