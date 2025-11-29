from typing import List, Dict
from uuid import uuid4
from ..state import GraphState
from ...agents.comment_triage import triage_comments
from ...core.models.comments import CommentScore, Comment
from ...core.models.evidence import Evidence, EvidenceType
from ...config.settings import settings


async def triage_node(state: GraphState) -> GraphState:
    """
    Triage Node: 对 state.comments 中的评论进行打分筛选，并将高价值评论晋升为 Evidence。
    Reads: state.comments, state.evidences
    Writes: state.comment_scores, state.evidences (promoted)
    """
    comments = state.get("comments", [])
    evidences = state.get("evidences", [])
    
    if not comments:
        return {
            "steps": ["triage: no comments to score"]
        }
    
    # 构建 Evidence 索引以便快速查找
    evidence_map = {e.id: e for e in evidences}
    
    # 按 evidence_id 分组评论
    comments_by_evidence: Dict[str, List[Comment]] = {}
    for c in comments:
        if c.evidence_id:
            if c.evidence_id not in comments_by_evidence:
                comments_by_evidence[c.evidence_id] = []
            comments_by_evidence[c.evidence_id].append(c)
            
    all_scores: List[CommentScore] = []
    promoted_evidences: List[Evidence] = []
    
    # 遍历分组进行打分
    for evidence_id, group_comments in comments_by_evidence.items():
        evidence = evidence_map.get(evidence_id)
        if not evidence:
            print(f"[WARN] Triage: Parent evidence {evidence_id} not found for comments")
            continue
            
        # 调用 Agent 进行打分
        scores = await triage_comments(evidence, group_comments)
        all_scores.extend(scores)
        
        # 晋升机制：将高分评论转换为 Evidence
        for score in scores:
            if score.total_score >= settings.comment_promotion_threshold:
                # 找到对应的原始评论
                original_comment = next((c for c in group_comments if c.id == score.comment_id), None)
                if original_comment:
                    new_evidence = Evidence(
                        id=str(uuid4()),
                        content=original_comment.content,
                        source=evidence.source, # 继承来源
                        type=EvidenceType.COMMENT,
                        author=original_comment.author,
                        publish_time=original_comment.publish_time,
                        metadata={
                            "origin": "comment_promotion",
                            "parent_evidence_id": evidence.id,
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
    
    steps = [f"triage: scored {len(all_scores)} comments"]
    if promoted_evidences:
        steps.append(f"triage: promoted {len(promoted_evidences)} comments to evidence")
        
    return {
        "comment_scores": all_scores,
        "evidences": promoted_evidences, # LangGraph 会自动将其追加到现有列表
        "steps": steps
    }
