
import pytest
import asyncio
from langchain_core.messages import AIMessage
from unittest.mock import AsyncMock, MagicMock, patch

from src.graph.state_v2 import WorkerState
from src.core.models.v2_structures import SearchConfiguration
from src.graph.nodes.worker_nodes import fetch_node_v2

@pytest.mark.asyncio
async def test_fetch_node_v2_query_generation_success():
    # 1. Mock Input State
    state = {"topic": "DeepSeek V3"}
    
    # 2. Mock LLM Response (Structured Query Config)
    mock_config = SearchConfiguration(
        queries=[
            "DeepSeek V3 release date",
            "DeepSeek V3 technical report",
            "DeepSeek V3 benchmarks"
        ],
        reasoning="Testing query generation"
    )
    
    # 3. Setup Mocks
    # We need to mock:
    # - search_model config in fetch_node_v2
    # - ChatOpenAI (or init_chat_model)
    # - LLM structured output
    # - tavily_search_tool.ainvoke
    
    with patch("src.graph.nodes.worker_nodes.init_chat_model") as mock_init, \
         patch("src.graph.nodes.worker_nodes.ChatOpenAI") as mock_chat_openai, \
         patch("src.graph.nodes.worker_nodes.tavily_search_tool") as mock_tavily, \
         patch("src.graph.nodes.worker_nodes.settings") as mock_settings:
        
        # Configure LLM Mock
        mock_llm = MagicMock()
        mock_generator = AsyncMock()
        
        mock_llm.with_structured_output.return_value = mock_generator
        mock_generator.ainvoke.return_value = mock_config
        
        mock_init.return_value = mock_llm
        mock_chat_openai.return_value = mock_llm
        
        # Configure Search Tool Mock
        mock_tavily.ainvoke = AsyncMock(return_value="Mocked Search Results")
        
        # Force Clean Path
        mock_settings.openai_base_url = None
        mock_settings.model_name = "gpt-4o"
        
        # 4. Run Node
        output = await fetch_node_v2(state, config={})
        
        # 5. Verify Output
        assert "messages" in output
        msg = output["messages"][0]
        content = msg.content
        
        print(f"DEBUG OUTPUT: {content}")
        
        # Verify Search Queries were logged
        assert "Search Queries Used:" in content
        assert "DeepSeek V3 release date" in content
        
        # Verify Tool Call used the GENERATED queries
        mock_tavily.ainvoke.assert_called_once()
        call_args = mock_tavily.ainvoke.call_args[0][0] # First arg (dict input)
        assert call_args["queries"] == mock_config.queries

@pytest.mark.asyncio
async def test_fetch_node_v2_generation_failure_fallback():
    # Test fallback to raw topic if LLM fails
    state = {"topic": "Fallback Topic"}
    
    with patch("src.graph.nodes.worker_nodes.init_chat_model") as mock_init, \
         patch("src.graph.nodes.worker_nodes.tavily_search_tool") as mock_tavily, \
         patch("src.graph.nodes.worker_nodes.settings") as mock_settings:
             
        mock_llm = MagicMock()
        mock_generator = AsyncMock()
        
        # Simulate Generator Failure
        mock_generator.ainvoke.side_effect = Exception("LLM Error")
        mock_llm.with_structured_output.return_value = mock_generator
        mock_init.return_value = mock_llm
        
        mock_tavily.ainvoke = AsyncMock(return_value="Fallback Results")
        
        mock_settings.openai_base_url = None
        
        output = await fetch_node_v2(state, config={})
        
        # Verify Tool Call used the FALLBACK topic
        mock_tavily.ainvoke.assert_called_once()
        call_args = mock_tavily.ainvoke.call_args[0][0]
        assert call_args["queries"] == ["Fallback Topic"]
