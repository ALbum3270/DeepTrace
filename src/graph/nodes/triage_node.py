from typing import List
from uuid import uuid4
from ..state import GraphState
from ...agents.comment_triage import triage_comments
from ...core.models.comments import CommentScore
from ...core.models.evidence import Evidence, EvidenceType
from ...config.settings import settings


async def triage_node(state: GraphState) -> GraphState:
    """
    Triage Node: 对证据中的评论进行打分筛选，并将高价值评论晋升为 Evidence。
    """
    evidences = state.get("evidences", [])
    
    if not evidences:
        return {
            "steps": ["triage: no evidences, skip"]
        }
        
    all_scores: List[CommentScore] = []
    promoted_evidences: List[Evidence] = []
    
    # 遍历所有证据，对有评论的证据进行打分
    for ev in evidences:
        if not ev.comments:
            continue
            
        # 调用 Agent 进行打分
        scores = await triage_comments(ev, ev.comments)
        all_scores.extend(scores)
        
        # 晋升机制：将高分评论转换为 Evidence
        # 注意：这些新 Evidence 本轮不会被 extract_node 处理，而是为下一轮或 Planner 准备
        for score in scores:
            if score.total_score >= settings.comment_promotion_threshold:
                # 找到对应的原始评论
                original_comment = next((c for c in ev.comments if c.id == score.comment_id), None)
                if original_comment:
                    new_evidence = Evidence(
                        id=str(uuid4()),
                        content=original_comment.content,
                        source=ev.source, # 继承来源
                        type=EvidenceType.COMMENT,
                        author=original_comment.author,
                        publish_time=original_comment.publish_time,
                        metadata={
                            "origin": "comment_promotion",
                            "parent_evidence_id": ev.id,
                            "comment_id": original_comment.id,
                            "triage_score": score.total_score,
                            "triage_dimensions": {
                                "novelty": score.novelty,
                                "evidence": score.evidence,
                                "contradiction": score.contradiction,
                                "influence": score.influence,
                                "coordination": score.coordination
                            }
                        }
                    )
                    promoted_evidences.append(new_evidence)
        
    if not all_scores:
        return {
            "steps": ["triage: no comments to score"]
        }
    
    steps = [f"triage: scored {len(all_scores)} comments"]
    if promoted_evidences:
        steps.append(f"triage: promoted {len(promoted_evidences)} comments to evidence")
        
    return {
        "comment_scores": all_scores,
        "evidences": promoted_evidences, # LangGraph 会自动将其追加到现有列表
        "steps": steps
    }
