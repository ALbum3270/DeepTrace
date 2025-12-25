import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import AIMessage
from src.graph.nodes.supervisor import supervisor_node
from src.core.models_v2 import ConductResearch, FinalAnswer

@pytest.mark.asyncio
async def test_supervisor_decisions():
    """Verify Supervisor logic (Tool Calling)."""
    
    # Mock LLM Response Helper
    def create_mock_response(tool_call_name: str, **kwargs):
        msg = AIMessage(content="Thinking...", tool_calls=[{
            "name": tool_call_name,
            "args": kwargs,
            "id": "call_123"
        }])
        return msg
        
    # Case 1: Need Research (Empty Context)
    mock_llm_research = MagicMock()
    mock_llm_research.bind_tools.return_value.ainvoke = AsyncMock(
        return_value=create_mock_response("ConductResearch", topic="Python Asyncio", reasoning="Need docs")
    )
    
    with patch("src.graph.nodes.supervisor.init_chat_model", return_value=mock_llm_research):
        state = {"objective": "How does Python Asyncio work?", "research_notes": []}
        result = await supervisor_node(state, config={})
        
        msg = result["messages"][0]
        assert msg.tool_calls[0]["name"] == "ConductResearch"
        assert msg.tool_calls[0]["args"]["topic"] == "Python Asyncio"

    # Case 2: Final Answer (Sufficient Context)
    mock_llm_final = MagicMock()
    mock_llm_final.bind_tools.return_value.ainvoke = AsyncMock(
        return_value=create_mock_response("FinalAnswer", content="Asyncio is...")
    )
    
    with patch("src.graph.nodes.supervisor.init_chat_model", return_value=mock_llm_final):
        # State with notes
        state = {
            "objective": "How does Python Asyncio work?", 
            "research_notes": ["Asyncio uses event loops."]
        }
        result = await supervisor_node(state, config={})
        
        msg = result["messages"][0]
        assert msg.tool_calls[0]["name"] == "FinalAnswer"
