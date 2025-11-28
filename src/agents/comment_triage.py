"""
Comment Triage Agent: 负责对评论进行多维度打分，筛选高价值线索。
"""
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from ..core.models.evidence import Evidence
from ..core.models.comments import Comment, CommentScore
from ..config.settings import settings
from .prompts import COMMENT_TRIAGE_SYSTEM_PROMPT
from ..llm.factory import init_llm


class CommentScoreInput(BaseModel):
    """LLM 只需要返回的评分字段。"""
    novelty: float = Field(..., ge=0.0, le=1.0, description="新颖性")
    evidence: float = Field(..., ge=0.0, le=1.0, description="证据性")
    contradiction: float = Field(..., ge=0.0, le=1.0, description="反驳性")
    influence: float = Field(..., ge=0.0, le=1.0, description="影响力")
    coordination: float = Field(..., ge=0.0, le=1.0, description="协调性")
    tags: List[str] = Field(default_factory=list, description="标签")
    reason: str = Field(default="", description="打分理由")
    rationale: str = Field(default="", description="LLM 给出的详细理由")


class CommentScoreBatch(BaseModel):
    """包装类，用于批量返回评分列表。"""
    scores: List[CommentScoreInput] = Field(description="评分列表")


async def triage_comments(evidence: Evidence, comments: List[Comment]) -> List[CommentScore]:
    """对指定证据下的评论列表进行打分。

    Args:
        evidence: 所属证据
        comments: 评论列表

    Returns:
        评分结表
    """
    if not comments:
        return []

    client = init_llm()

    # 将评论列表转为带序号的文本，便于 LLM 对应
    comments_text = "\n".join([f"[{i+1}] {c.content}" for i, c in enumerate(comments)])

    user_message = f"""Evidence Content: {evidence.content}

Comments to Triage:
{comments_text}

请对以上 {len(comments)} 条评论进行评分。请确保返回的 scores 列表顺序与输入评论顺序一致。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", COMMENT_TRIAGE_SYSTEM_PROMPT),
        ("user", user_message)
    ])

    try:
        # 使用包装类来避免泛型类型问题
        structured_llm = client.with_structured_output(CommentScoreBatch)
        chain = prompt | structured_llm
        result = await chain.ainvoke({})

        final_scores: List[CommentScore] = []
        if result and result.scores:
            for i, score_input in enumerate(result.scores):
                if i >= len(comments):
                    break
                cs = CommentScore(
                    evidence_id=evidence.id,
                    comment_id=comments[i].id,
                    novelty=score_input.novelty,
                    evidence=score_input.evidence,
                    contradiction=score_input.contradiction,
                    influence=score_input.influence,
                    coordination=score_input.coordination,
                    tags=score_input.tags,
                    reason=score_input.reason,
                    rationale=score_input.rationale,
                )
                cs.calculate_total()
                final_scores.append(cs)
        return final_scores
    except Exception as e:
        # 尝试容错处理：如果 LLM 返回了列表而非对象
        error_msg = str(e)
        if "Input should be an object" in error_msg and "input_type=list" in error_msg:
            print(f"[WARN] Comment triage returned a list instead of object, attempting to fix...")
            try:
                # 再次调用（或者如果能获取到 raw output 更好，但这里简单起见重新尝试解析或直接用 raw chain）
                # 由于 with_structured_output 已经失败，我们需要用 raw chain 获取内容
                raw_chain = prompt | client
                raw_result = await raw_chain.ainvoke({})
                import json
                content = raw_result.content if hasattr(raw_result, 'content') else str(raw_result)
                data = json.loads(content)
                
                # 如果 data 本身就是 list
                if isinstance(data, list):
                    final_scores = []
                    for i, item in enumerate(data):
                        if i >= len(comments): break
                        # 转换为 CommentScoreInput (简单字典访问)
                        cs = CommentScore(
                            evidence_id=evidence.id,
                            comment_id=comments[i].id,
                            novelty=item.get("novelty", 0.0),
                            evidence=item.get("evidence", 0.0),
                            contradiction=item.get("contradiction", 0.0),
                            influence=item.get("influence", 0.0),
                            coordination=item.get("coordination", 0.0),
                            tags=item.get("tags", []),
                            reason=item.get("reason", ""),
                            rationale=item.get("rationale", "")
                        )
                        cs.calculate_total()
                        final_scores.append(cs)
                    return final_scores
            except Exception as e2:
                print(f"[ERROR] Fallback triage failed: {e2}")

        print(f"[ERROR] Comment triage failed for evidence {evidence.id}: {e}")
        import traceback
        traceback.print_exc()
        return []
