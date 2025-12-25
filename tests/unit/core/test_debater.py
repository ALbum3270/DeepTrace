
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.core.tools.debater import debater_tool
from langchain_core.messages import AIMessage

@pytest.mark.asyncio
async def test_debater_tool_logic():
    """Verify Debater Tool invokes LLM with correct prompt."""
    
    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Verdict: Claim A is true due to recency."))
    
    with patch("src.core.tools.debater.init_chat_model", return_value=mock_llm), patch(
        "src.core.tools.debater.safe_ainvoke", new_callable=AsyncMock
    ) as mock_safe:
        mock_safe.return_value = AIMessage(content="### Verdict Analysis for Python 4.0\nVerdict: Claim A is true")

        result = await debater_tool.ainvoke({
            "topic": "Python 4.0", 
            "claims": ["Released in 2024", "Release canceled"],
            "source_ids": ["SourceA", "SourceB"]
        })

        # Verify Output contains topic + verdict structure
        assert "Python 4.0" in result
        assert "Verdict" in result or "verdict" in result

        # safe_ainvoke should be called at least once (two debate rounds + judge)
        assert mock_safe.call_count >= 1
        
    # Verify Prompt Construction
    # Judge prompt should include sources
    found_sources = False
    for call in mock_safe.call_args_list:
        # safe_ainvoke is called as safe_ainvoke(llm, messages, model_name=...)
        messages = call[0][1]
        if len(messages) == 2 and "Lead Editor and Fact Checker" in messages[0].content:
            assert "SourceA" in messages[1].content
            assert "SourceB" in messages[1].content
            found_sources = True
            break
    assert found_sources, "Judge prompt not found in LLM calls"
