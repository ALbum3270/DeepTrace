

import pytest
import asyncio
from langchain_core.messages import AIMessage
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models.v2_structures import ExtractionResult, ExtractedEvent
from src.graph.nodes.worker_nodes import extract_node_v2

@pytest.mark.asyncio
async def test_extract_node_v2_success():
    # 1. Mock Input State
    state = {
        "messages": [
            AIMessage(content="Search Result: OpenAI announced GPT-5 on 2024-12-25. It is powerful.")
        ]
    }
    
    # 2. Mock LLM Response (Structured)
    mock_event = ExtractedEvent(
        date="2024-12-25",
        title="GPT-5 Announced",
        description="OpenAI announced GPT-5 which is powerful.",
        source_url="http://openai.com",
        confidence=0.95
    )
    mock_result = ExtractionResult(events=[mock_event])
    
    # 3. Setup Mock LLM
    # We patch BOTH init_chat_model and ChatOpenAI to be safe, covering both paths.
    with patch("src.graph.nodes.worker_nodes.init_chat_model") as mock_init, \
         patch("src.graph.nodes.worker_nodes.ChatOpenAI") as mock_chat_openai, \
         patch("src.graph.nodes.worker_nodes.settings") as mock_settings:
        
        # Configure Mocks
        mock_llm = MagicMock()
        mock_extractor = AsyncMock()
        
        # Chain setup: llm.with_structured_output(...) -> extractor
        mock_llm.with_structured_output.return_value = mock_extractor
        mock_extractor.ainvoke.return_value = mock_result
        
        # Apply to both factory methods
        mock_init.return_value = mock_llm
        mock_chat_openai.return_value = mock_llm
        
        # Force one path or allow both (logic in code handles it)
        # Check logic: if settings.openai_base_url ...
        mock_settings.openai_base_url = None # Force init_chat_model path for simplicity
        mock_settings.model_name = "gpt-4o"
        
        # 4. Run Node
        output = await extract_node_v2(state, config={})
        
        # 5. Verify
        assert "messages" in output
        result_msg = output["messages"][0]
        assert isinstance(result_msg, AIMessage)
        content = result_msg.content
        
        print(f"DEBUG OUTPUT: {content}")
        
        assert "extracted_events:" in content
        assert "[EVENT] 2024-12-25 | GPT-5 Announced" in content
        assert "(Source: http://openai.com)" in content

@pytest.mark.asyncio
async def test_extract_node_v2_empty_input():
    state = {"messages": []}
    output = await extract_node_v2(state, config={})
    assert output == {"research_notes": "No search results to extract from."}

@pytest.mark.asyncio
async def test_extract_node_v2_llm_failure():
    state = {
        "messages": [AIMessage(content="Some content")]
    }
    
    with patch("src.graph.nodes.worker_nodes.init_chat_model") as mock_init, \
         patch("src.graph.nodes.worker_nodes.settings") as mock_settings:
        
        mock_settings.openai_base_url = None
        
        mock_llm = MagicMock()
        mock_extractor = AsyncMock()
        mock_extractor.ainvoke.side_effect = Exception("API Error")
        mock_llm.with_structured_output.return_value = mock_extractor
        mock_init.return_value = mock_llm
        
        output = await extract_node_v2(state, config={})
        
        assert "messages" in output
        assert "Extraction failed" in output["messages"][0].content
