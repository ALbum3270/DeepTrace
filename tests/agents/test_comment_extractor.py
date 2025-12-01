import sys
import os
sys.path.append(os.getcwd())
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.comment_extractor import extract_comments_from_article
from src.core.models.evidence import Evidence, EvidenceType

@pytest.mark.asyncio
async def test_extract_comments_logic():
    # Case 1: Empty content
    evidence = Evidence(
        id="ev1",
        title="Test", 
        content="", 
        url="http://test.com", 
        source="news", 
        type=EvidenceType.ARTICLE
    )
    comments = await extract_comments_from_article(evidence)
    assert comments == []
    
    # Case 2: Short content
    evidence.content = "Short content"
    comments = await extract_comments_from_article(evidence)
    assert comments == []

@pytest.mark.asyncio
async def test_extract_comments_success():
    # Case 3: Valid content with Mock LLM
    evidence = Evidence(
        id="ev_valid",
        title="Valid Article",
        content="Some content...",
        full_content="Full content " * 50, # Long enough
        url="http://example.com/article",
        source="news",
        type=EvidenceType.ARTICLE
    )
    
    mock_llm_response = {
        "comments": [
            {
                "content": "This is a public opinion",
                "author": "Netizen A",
                "role": "public_opinion"
            },
            {
                "content": "Official statement",
                "author": "Spokesperson",
                "role": "direct_quote"
            }
        ]
    }
    
    # Mock the chain execution flow
    # chain = prompt | llm | parser
    
    mock_chain = AsyncMock()
    mock_chain.ainvoke.return_value = mock_llm_response
    
    # Mock the intermediate objects
    mock_prompt = MagicMock()
    mock_llm = MagicMock()
    mock_parser = MagicMock()
    
    # Setup the pipe behavior
    # prompt | llm -> intermediate
    # intermediate | parser -> chain
    
    mock_intermediate = MagicMock()
    mock_prompt.__or__.return_value = mock_intermediate
    mock_intermediate.__or__.return_value = mock_chain
    
    # Also handle the case where llm | parser is done differently or if init_llm returns something else
    # But generally prompt | llm is the first step.
    
    with patch("src.agents.comment_extractor.ChatPromptTemplate") as MockPromptClass:
        MockPromptClass.from_messages.return_value = mock_prompt
        
        with patch("src.agents.comment_extractor.init_llm", return_value=mock_llm):
            with patch("src.agents.comment_extractor.JsonOutputParser", return_value=mock_parser):
                
                # We need to ensure prompt | llm works. 
                # Since prompt is a mock, prompt | llm calls prompt.__or__(llm)
                
                comments = await extract_comments_from_article(evidence)
                
                # Debug if failed
                if not comments:
                    print("DEBUG: Comments are empty. Chain execution failed.")
                
                assert len(comments) == 2
                assert comments[0].content == "This is a public opinion"
                assert comments[0].role == "public_opinion"
                assert comments[0].source_evidence_id == "ev_valid"
                
                assert comments[1].content == "Official statement"
                assert comments[1].role == "direct_quote"
                assert comments[1].source_evidence_id == "ev_valid"
