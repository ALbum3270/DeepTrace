import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.graph.subgraphs.worker import build_worker_subgraph

# NOTE: AsyncMock is available in unittest.mock in Python 3.8+
# No need for custom helper if environment supports it, but keeping it safe.
# Actually stdlib AsyncMock is better.


@pytest.mark.asyncio
async def test_worker_subgraph_flow():
    """Verify detailed internal flow of Worker Subgraph."""

    mock_search_results = [
        {
            "query": "Python",
            "results": [
                {
                    "title": "Python.org",
                    "url": "http://python.org",
                    "content": "Python is great.",
                }
            ],
        }
    ]

    mock_llm_response = MagicMock(content="Compressed: Python is good.")
    mock_llm = MagicMock()
    mock_llm.with_retry.return_value.ainvoke = AsyncMock(return_value=mock_llm_response)

    target_patch = "src.core.tools.search.tavily_search_async"
    print(f"\nDEBUG: Patching {target_patch}")

    # Use new_callable=AsyncMock for robust async function patching
    with (
        patch(target_patch, new_callable=AsyncMock) as mock_search_func,
        patch(
            "src.graph.nodes.compressor.init_chat_model", return_value=mock_llm
        ) as mock_init,
        patch(
            "src.graph.nodes.compressor.ChatOpenAI", return_value=mock_llm, create=True
        ) as mock_chatopenai,
    ):
        # Configure return value
        mock_search_func.return_value = mock_search_results

        # 1. Build Graph
        app = build_worker_subgraph()

        # 2. Input State
        initial_state = {"topic": "Python", "messages": [], "research_notes": ""}

        # 3. Invocation
        final_state = await app.ainvoke(initial_state)

        # 4. Verify Nodes Executed
        assert mock_search_func.called, "Search function was not called"

        # Ensure pipeline produced notes (compressor executed)
        assert final_state.get("research_notes"), "Research notes missing from worker output"

        # 5. Verify Output State
        # Check messages for content
        assert len(final_state["messages"]) > 0
        last_msg = final_state["messages"][0]
        print(f"DEBUG: Last Msg Content: {last_msg.content}")
        assert "Python.org" in last_msg.content
        assert "Python is great" in last_msg.content

        # Check Compressor Output is non-empty (content may vary with prompt)
        assert final_state["research_notes"].strip(), "Compressed notes should not be empty"
