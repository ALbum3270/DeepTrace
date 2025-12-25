import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from src.graph.state_v2 import WorkerState
from src.graph.nodes.compressor import compress_node


# Async Mock Helper
class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)


@pytest.mark.asyncio
async def test_compress_node_success():
    """Verify that compress_node calls LLM and returns compressed notes when content is long."""

    # 1. Mock State (force compression by exceeding threshold)
    long_text = "Apple " * 3000
    mock_state: WorkerState = {
        "topic": "Test Topic",
        "messages": [
            HumanMessage(content=long_text),
            AIMessage(content="Apple is a fruit."),
        ],
        "research_notes": "",
        "timeline": [],
    }
    mock_config = {"configurable": {"summarization_model": "gpt-4o"}}

    # 2. Mock LLM
    mock_response = AIMessage(content="Compressed Note: Apple is a tasty fruit [1].")

    with patch("src.graph.nodes.compressor.init_chat_model") as mock_init, patch(
        "src.graph.nodes.compressor.safe_ainvoke", new_callable=AsyncMock
    ) as mock_safe:
        mock_llm = MagicMock()
        mock_llm_with_retry = MagicMock()
        mock_llm_with_retry.ainvoke = AsyncMock(return_value=mock_response)

        mock_llm.with_retry.return_value = mock_llm_with_retry
        mock_init.return_value = mock_llm
        mock_safe.return_value = mock_response

        # 3. Execute Node
        result = await compress_node(mock_state, mock_config)

        # 4. Verify
        assert "research_notes" in result
        assert (
            result["research_notes"] == "Compressed Note: Apple is a tasty fruit [1]."
        )

        # Verify model init and safety wrapper usage
        mock_init.assert_called_once_with(model="gpt-4o", temperature=0)
        mock_safe.assert_called_once()


@pytest.mark.asyncio
async def test_compress_node_short_circuit_returns_raw():
    """When content is short, compressor should skip LLM and return raw history."""

    mock_state: WorkerState = {
        "topic": "Short",
        "messages": [HumanMessage(content="Short content"), AIMessage(content="More" )],
        "research_notes": "",
        "timeline": [],
    }

    with patch("src.graph.nodes.compressor.init_chat_model") as mock_init, patch(
        "src.graph.nodes.compressor.safe_ainvoke", new_callable=AsyncMock
    ) as mock_safe:
        result = await compress_node(mock_state, {})

        # Should return concatenated raw content and avoid any LLM calls
        assert result["research_notes"].startswith("Short content")
        mock_init.assert_not_called()
        mock_safe.assert_not_called()


@pytest.mark.asyncio
async def test_compress_node_empty():
    """Verify behavior when messages are empty."""
    mock_state: WorkerState = {
        "topic": "Empty",
        "messages": [],  # Empty history
        "research_notes": "",
        "timeline": [],
    }
    mock_config = {}

    result = await compress_node(mock_state, mock_config)
    assert result["research_notes"] == "No research performed."
