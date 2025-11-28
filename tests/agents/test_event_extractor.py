"""
测试 Event Extractor Agent
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from src.core.models.evidence import Evidence, EvidenceSource
from src.core.models.events import EventNode, EventStatus
from src.agents.event_extractor import extract_event_from_evidence

class TestEventExtractor:
    """测试事件提取 Agent"""
    
    @pytest.mark.asyncio
    async def test_extract_event_success(self):
        """测试成功提取"""
        evidence = Evidence(
            content="2023年10月1日，品牌方发布了致歉声明。",
            source=EvidenceSource.WEIBO,
            publish_time=datetime(2023, 10, 1, 12, 0, 0)
        )
        
        expected_event = EventNode(
            title="品牌方发布致歉声明",
            description="品牌方在微博发布了致歉声明。",
            time=datetime(2023, 10, 1, 12, 0, 0),
            status=EventStatus.CONFIRMED,
            actors=["品牌方"]
        )

        with patch("src.agents.event_extractor.init_llm") as mock_init, \
             patch("src.agents.event_extractor.ChatPromptTemplate") as mock_prompt_cls:
            # Mock LLM
            mock_llm = MagicMock()
            mock_init.return_value = mock_llm
            mock_structured_llm = MagicMock()
            mock_llm.with_structured_output.return_value = mock_structured_llm
            
            # Mock Prompt and Chain
            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt
            mock_chain = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            # Make ainvoke async
            mock_chain.ainvoke = AsyncMock(return_value=expected_event)
            
            result = await extract_event_from_evidence(evidence)
            
            assert result is not None
            assert result.title == "品牌方发布致歉声明"
            assert result.evidence_ids == [evidence.id]
            mock_chain.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_extract_event_failure(self):
        """测试提取失败"""
        evidence = Evidence(content="无效内容")
        
        with patch("src.agents.event_extractor.init_llm") as mock_init, \
             patch("src.agents.event_extractor.ChatPromptTemplate") as mock_prompt_cls:
            mock_llm = MagicMock()
            mock_init.return_value = mock_llm
            
            mock_prompt = MagicMock()
            mock_prompt_cls.from_messages.return_value = mock_prompt
            mock_chain = MagicMock()
            mock_prompt.__or__.return_value = mock_chain
            # Simulate async exception
            mock_chain.ainvoke = AsyncMock(side_effect=Exception("API Error"))
            
            result = await extract_event_from_evidence(evidence)
            assert result is None
