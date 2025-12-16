
import pytest
import datetime
from typing import List
from src.core.models.events import EventNode
from src.core.verification.clustering import TimelineClusterer, EventCluster

# Mock Embeddings
class MockEmbeddings:
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Return mock vectors based on simple string matching for test determinism
        # "Apple" -> [1.0, 0.0]
        # "Banana" -> [0.0, 1.0]
        vectors = []
        for text in texts:
            if "Apple" in text:
                vectors.append([1.0, 0.0])
            elif "Banana" in text:
                vectors.append([0.0, 1.0])
            else:
                vectors.append([0.5, 0.5]) # Low similarity to both
        return vectors
        
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed_documents(texts)

@pytest.mark.asyncio
async def test_timeline_clustering_logic():
    """测试聚类核心逻辑：时间窗口 + 语义相似度"""
    
    # Setup Data
    base_time = datetime.datetime(2023, 1, 1)
    
    # Cluster 1: Apples (Week 1)
    e1 = EventNode(title="Apple 1", description="Apple release", time=base_time)
    e2 = EventNode(title="Apple 2", description="Apple sales", time=base_time + datetime.timedelta(days=2))
    
    # Cluster 2: Bananas (Week 1) - Similar time, different topic
    e3 = EventNode(title="Banana 1", description="Banana harvest", time=base_time + datetime.timedelta(days=1))
    
    # Cluster 3: Apples (Month later) - Same topic, different time
    e4 = EventNode(title="Apple 3", description="Apple earnings", time=base_time + datetime.timedelta(days=30))
    
    events = [e1, e2, e3, e4]
    
    # Init Clusterer with Mock Embeddings
    clusterer = TimelineClusterer(time_window_days=7, sim_threshold=0.8)
    clusterer.embeddings_model = MockEmbeddings() # Inject Mock
    
    # Execute
    clusters = await clusterer.cluster_events(events)
    
    # Assertions
    # Expect 3 clusters:
    # 1. [Apple 1, Apple 2] (High Sim, Close Time)
    # 2. [Banana 1] (Low Sim to apples, though close time)
    # 3. [Apple 3] (High Sim to apples, but far time)
    
    assert len(clusters) == 3
    
    # Verify groupings
    # Cluster 1 should have 2 events
    c1 = next((c for c in clusters if len(c.events) == 2), None)
    assert c1 is not None
    titles = [e.title for e in c1.events]
    assert "Apple 1" in titles
    assert "Apple 2" in titles
    
    # Banana should be alone
    banana_cluster = next((c for c in clusters if c.events[0].title == "Banana 1"), None)
    assert len(banana_cluster.events) == 1
    
    # Apple 3 should be alone
    apple3_cluster = next((c for c in clusters if c.events[0].title == "Apple 3"), None)
    assert len(apple3_cluster.events) == 1

@pytest.mark.asyncio
async def test_empty_events():
    clusterer = TimelineClusterer()
    clusters = await clusterer.cluster_events([])
    assert len(clusters) == 0
