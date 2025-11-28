"""
测试 Retrieval Planner Agent
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.models.evidence import Evidence, EvidenceSource
from src.core.models.timeline import Timeline
from src.core.models.plan import RetrievalPlan, SearchQuery
from src.agents.retrieval_planner import plan_retrieval

class TestRetrievalPlanner:
    """测试检索规划 Agent"""

    @pytest.fixture
    def mock_timeline(self):
        return Timeline(events=[], open_questions=[])

    @pytest.fixture
    def mock_evidences(self):
        return [Evidence(content="test", source=EvidenceSource.NEWS)]

    @pytest.mark.asyncio
    async def test_plan_retrieval_success(self, mock_timeline, mock_evidences):
        """测试成功生成检索计划"""
        expected_plan = RetrievalPlan(
            queries=[SearchQuery(query="test query", rationale="test rationale")],
            thought_process="thinking",
            finish=False
        )

        with patch("src.agents.retrieval_planner.init_llm") as mock_init, \
             patch("src.agents.retrieval_planner.ChatPromptTemplate") as mock_prompt_cls:
            
            # Mock LLM and Chain
            mock_llm = MagicMock()
            mock_init.return_value = mock_llm
            mock_structured_llm = MagicMock()
            mock_llm.with_structured_output.return_value = mock_structured_llm
            
            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt
            
            mock_chain = MagicMock()
            # Note: In the implementation, we do: chain = prompt | structured_llm
            # So we need to mock the result of the pipe operation or the chain execution
            # But wait, in the implementation: chain = prompt | structured_llm
            # We can mock prompt.__or__ to return mock_chain
            mock_prompt.__or__.return_value = mock_chain
            
            mock_chain.ainvoke = AsyncMock(return_value=expected_plan)

            result = await plan_retrieval(mock_timeline, mock_evidences)

            assert result == expected_plan
            assert len(result.queries) == 1
            assert result.queries[0].query == "test query"
            assert result.finish is False

    @pytest.mark.asyncio
    async def test_plan_retrieval_fallback(self, mock_timeline, mock_evidences):
        """测试结构化输出失败后的容错处理（字符串列表）"""
        
        # 模拟第一次结构化输出失败
        with patch("src.agents.retrieval_planner.init_llm") as mock_init, \
             patch("src.agents.retrieval_planner.ChatPromptTemplate") as mock_prompt_cls:
            
            mock_llm = MagicMock()
            mock_init.return_value = mock_llm
            
            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt
            
            # 第一次 chain (structured) 抛出异常
            mock_structured_chain = MagicMock()
            mock_structured_chain.ainvoke = AsyncMock(side_effect=Exception("Input should be an object ... queries ..."))
            
            # 第二次 chain (raw) 返回包含字符串列表的 JSON
            mock_raw_chain = MagicMock()
            mock_raw_result = MagicMock()
            mock_raw_result.content = '{"queries": ["string query"], "thought_process": "fallback", "finish": false}'
            mock_raw_chain.ainvoke = AsyncMock(return_value=mock_raw_result)
            
            # 设置 prompt | ... 的返回值
            # 第一次调用 prompt | structured_llm -> mock_structured_chain
            # 第二次调用 prompt | client -> mock_raw_chain
            mock_prompt.__or__.side_effect = [mock_structured_chain, mock_raw_chain]

            result = await plan_retrieval(mock_timeline, mock_evidences)

            assert result.finish is False
            assert len(result.queries) == 1
            assert result.queries[0].query == "string query"
            assert result.queries[0].rationale == "自动生成（LLM 返回格式不符）"

    @pytest.mark.asyncio
    async def test_plan_retrieval_complete_failure(self, mock_timeline, mock_evidences):
        """测试完全失败的情况"""
        with patch("src.agents.retrieval_planner.init_llm") as mock_init, \
             patch("src.agents.retrieval_planner.ChatPromptTemplate") as mock_prompt_cls:
            
            mock_llm = MagicMock()
            mock_init.return_value = mock_llm
            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt
            
            # 两次都失败
            mock_chain = MagicMock()
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("Total Failure"))
            mock_prompt.__or__.return_value = mock_chain

            result = await plan_retrieval(mock_timeline, mock_evidences)

            assert result.finish is True
            assert len(result.queries) == 0
            assert "Planning failed" in result.thought_process
