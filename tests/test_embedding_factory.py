
import pytest
from src.llm.factory import init_embeddings
from src.config.settings import settings

def test_init_embeddings_config():
    """测试 embedding 初始化配置是否正确读取 settings"""
    embeddings = init_embeddings()
    assert embeddings.model == settings.embedding_model_name
    assert embeddings.openai_api_base == settings.openai_base_url
    assert embeddings.openai_api_key.get_secret_value() == settings.openai_api_key

@pytest.mark.asyncio
async def test_embed_query_execution():
    """测试实际 Embedding 调用 (需要 API Key)"""
    # 如果没有配 Key 跳过 test
    if not settings.openai_api_key:
        pytest.skip("No API Key provided")
        
    embeddings = init_embeddings()
    text = "DeepTrace Phase 20 Verification Swarm"
    
    # Test synchronous call
    vector = embeddings.embed_query(text)
    
    # OpenAI text-embedding-3-small dimension is 1536
    # different models have different dimensions, just check it's a list of floats
    assert isinstance(vector, list)
    assert len(vector) > 0
    assert isinstance(vector[0], float)
    
    print(f"Embedding dimension: {len(vector)}")

@pytest.mark.asyncio
async def test_embed_documents_execution():
    """测试批量文档 Embedding"""
    if not settings.openai_api_key:
        pytest.skip("No API Key provided")
        
    embeddings = init_embeddings()
    texts = ["Test Document 1", "Test Document 2"]
    
    vectors = embeddings.embed_documents(texts)
    
    assert isinstance(vectors, list)
    assert len(vectors) == 2
    assert len(vectors[0]) > 0
