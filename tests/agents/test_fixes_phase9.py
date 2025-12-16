import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.report_writer import write_narrative_report
from src.agents.timeline_deduplicator import rewrite_and_merge_event
from src.core.models.events import EventNode
from src.core.models.evidence import Evidence
from src.core.models.timeline import Timeline
from src.core.models.strategy import SearchStrategy
from src.graph.workflow import should_continue
from src.core.models.plan import RetrievalPlan, SearchQuery

@pytest.mark.asyncio
async def test_report_writer_truncation_fix():
    """Verify that report writer accepts more than 20 evidences."""
    # Mock LLM
    with patch("src.agents.report_writer.init_llm"):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = "Report Content"
        # Mock chain
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = "Report Content"
        # Mock prompt | llm
        mock_prompt = MagicMock()
        mock_prompt.__or__.return_value = mock_chain
        
        with patch("src.agents.report_writer.ChatPromptTemplate") as mock_template:
            mock_template.from_messages.return_value = mock_prompt
            
            # Create 50 evidences
            evidences = [Evidence(url=f"http://test.com/{i}", content=f"Content {i}", source="news") for i in range(50)]
            timeline = Timeline(events=[])
            
            await write_narrative_report("Topic", timeline, evidences)
            
            # Check if the prompt contains evidence #49 (index 49, so "证据 50")
            # We can inspect the call args of prompt.from_messages
            call_args = mock_template.from_messages.call_args
            assert call_args is not None
            messages = call_args[0][0]
            user_msg = messages[1][1]
            
            assert "**证据 50**" in user_msg
            assert "仅展示前20条" not in user_msg # Should not have the old warning text if we removed it, or at least check count

@pytest.mark.asyncio
async def test_fusion_rewrite_logic():
    """Verify rewrite_and_merge_event calls LLM."""
    target = EventNode(id="1", title="News Title", description="News Fact", source="News", confidence=0.9)
    source = EventNode(id="2", title="Social Title", description="Social Opinion", source="Weibo", confidence=0.6)
    
    with patch("src.agents.timeline_deduplicator.init_llm"):
        AsyncMock()
        # Mock chain | StrOutputParser
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = "Fused Description"
        
        with patch("src.agents.timeline_deduplicator.ChatPromptTemplate") as mock_template:
            mock_template.from_messages.return_value = MagicMock()
            mock_template.from_messages.return_value.__or__.return_value = MagicMock()
            mock_template.from_messages.return_value.__or__.return_value.__or__.return_value = mock_chain
            
            await rewrite_and_merge_event(target, source)
            
            assert target.description == "Fused Description"
            assert target.source == "News" # Priority check

def test_strategy_reversion_fix():
    """Verify should_continue returns correct node based on strategy."""
    # Case 1: WEIBO strategy
    state_weibo = {
        "retrieval_plan": RetrievalPlan(queries=[SearchQuery(query="q", rationale="r")], finish=False, thought_process="test"),
        "search_strategy": SearchStrategy.WEIBO,
        "loop_step": 0,
        "max_loops": 3
    }
    assert should_continue(state_weibo) == "weibo_fetch"
    
    # Case 2: GENERIC strategy
    state_generic = {
        "retrieval_plan": RetrievalPlan(queries=[SearchQuery(query="q", rationale="r")], finish=False, thought_process="test"),
        "search_strategy": SearchStrategy.GENERIC,
        "loop_step": 0,
        "max_loops": 3
    }
    assert should_continue(state_generic) == "fetch"
    
    # Case 3: MIXED strategy
    state_mixed = {
        "retrieval_plan": RetrievalPlan(queries=[SearchQuery(query="q", rationale="r")], finish=False, thought_process="test"),
        "search_strategy": SearchStrategy.MIXED,
        "loop_step": 0,
        "max_loops": 3
    }
    assert should_continue(state_mixed) == "mixed_entry"
