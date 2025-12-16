
import logging
from typing import Dict, Any

from ..state import GraphState
from ...agents.report_writer import write_narrative_report

logger = logging.getLogger(__name__)

async def report_node(state: GraphState) -> Dict[str, Any]:
    """
    Reporter Node: 生成最终调查报告
    """
    state.get("events", []) # Unused directly, inside timeline
    timeline = state.get("timeline")
    claims = state.get("claims", [])
    evidences = state.get("evidences", [])
    
    # Collect remaining tasks (Unexplored)
    breadth_pool = state.get("breadth_pool", [])
    depth_pool = state.get("depth_pool", [])
    
    remaining_tasks = []
    for t in breadth_pool:
        remaining_tasks.append(f"Breadth Task (VoI {t.voi_score:.2f}): {t.query}")
    for t in depth_pool:
        # Assuming we can resolve claim content here or just ID
        remaining_tasks.append(f"Depth Task (VoI {t.voi_score:.2f}): Claim {t.claim_id}")
    
    # 模拟 User Context (从 initial_query 或 current_query)
    user_query = state.get("initial_query") or state.get("current_query") or "Topic"
    
    if not timeline:
        return {
            "final_report": "Error: No timeline generated.",
            "steps": ["reporter: no timeline"]
        }
    
    try:
        # Correct Signature: topic, timeline, evidences, claims
        report_content = await write_narrative_report(
            topic=user_query,
            timeline=timeline,
            evidences=evidences,
            claims=claims,
            remaining_tasks=remaining_tasks
        )
        
        return {
            "final_report": report_content,
            "steps": ["reporter: report generated"]
        }
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return {
            "final_report": f"Report generation failed: {e}",
            "steps": ["reporter: failed"]
        }
