"""
测试 Comment Triage Agent
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.models.evidence import Evidence, EvidenceSource
from src.core.models.comments import Comment
from src.agents.comment_triage import triage_comments, CommentScoreBatch, CommentScoreInput

class TestCommentTriage:
    """测试评论分拣 Agent"""

    @pytest.fixture
    def mock_evidence(self):
        return Evidence(content="test evidence", source=EvidenceSource.WEIBO)

    @pytest.fixture
    def mock_comments(self):
        return [
            Comment(id="c1", content="comment 1", author="user1", platform="weibo", evidence_id="e1"),
            Comment(id="c2", content="comment 2", author="user2", platform="weibo", evidence_id="e1")
        ]

    @pytest.mark.asyncio
    async def test_triage_comments_success(self, mock_evidence, mock_comments):
        """测试成功评分"""
        
        # 构造预期的结构化输出
        score_input1 = CommentScoreInput(
            novelty=0.8, evidence=0.5, contradiction=0.0, influence=0.1, coordination=0.0,
            tags=["tag1"], reason="reason1", rationale="rationale1"
        )
        score_input2 = CommentScoreInput(
            novelty=0.1, evidence=0.1, contradiction=0.0, influence=0.0, coordination=0.0,
            tags=[], reason="reason2", rationale="rationale2"
        )
        expected_batch = CommentScoreBatch(scores=[score_input1, score_input2])

        with patch("src.agents.comment_triage.init_llm") as mock_init, \
             patch("src.agents.comment_triage.ChatPromptTemplate") as mock_prompt_cls:
            
            mock_llm = MagicMock()
            mock_init.return_value = mock_llm
            mock_structured_llm = MagicMock()
            mock_llm.with_structured_output.return_value = mock_structured_llm
            
            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt
            
            mock_chain = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            mock_chain.ainvoke = AsyncMock(return_value=expected_batch)

            results = await triage_comments(mock_evidence, mock_comments)

            assert len(results) == 2
            assert results[0].comment_id == "c1"
            assert results[0].novelty == 0.8
            assert results[1].comment_id == "c2"
            assert results[1].novelty == 0.1

    @pytest.mark.asyncio
    async def test_triage_comments_fallback(self, mock_evidence, mock_comments):
        """测试结构化输出失败后的容错处理（列表返回）"""
        
        with patch("src.agents.comment_triage.init_llm") as mock_init, \
             patch("src.agents.comment_triage.ChatPromptTemplate") as mock_prompt_cls:
            
            mock_llm = MagicMock()
            mock_init.return_value = mock_llm
            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt
            
            # 第一次 chain (structured) 抛出特定异常
            mock_structured_chain = MagicMock()
            mock_structured_chain.ainvoke = AsyncMock(side_effect=Exception("Input should be an object ... input_type=list"))
            
            # 第二次 chain (raw) 返回 JSON 列表
            mock_raw_chain = MagicMock()
            mock_raw_result = MagicMock()
            # 模拟 LLM 直接返回了列表
            mock_raw_result.content = '[{"novelty": 0.9, "evidence": 0.5, "contradiction": 0.0, "influence": 0.0, "coordination": 0.0}]'
            mock_raw_chain.ainvoke = AsyncMock(return_value=mock_raw_result)
            
            mock_prompt.__or__.side_effect = [mock_structured_chain, mock_raw_chain]

            results = await triage_comments(mock_evidence, mock_comments[:1])

            assert len(results) == 1
            assert results[0].novelty == 0.9

    @pytest.mark.asyncio
    async def test_triage_comments_empty(self, mock_evidence):
        """测试空评论列表"""
        results = await triage_comments(mock_evidence, [])
        assert results == []
