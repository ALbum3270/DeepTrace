"""
Timeline Retrieval & Clustering Module.
Implements 'Hardware Point 8': Time-Window (±7d) + Embedding Cosine + Union-Find.
"""
import numpy as np
from datetime import timedelta
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from ..models.events import EventNode
from ...llm.factory import init_embeddings

class EventCluster(BaseModel):
    """Event Cluster: A group of semantically and temporally related events."""
    id: str
    events: List[EventNode]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    summary_embedding: Optional[List[float]] = Field(None, description="Centroid embedding (optional)")
    representative_title: str = Field(default="", description="Auto-generated title from most central event")

    def __len__(self):
        return len(self.events)

class TimelineClusterer:
    """
    Clusters events based on:
    1. Temporal proximity (Hard constraint: ±7 days)
    2. Semantic similarity (Hard constraint: Cosine > 0.85)
    3. Union-Find (Transitive closure)
    """
    
    def __init__(self, time_window_days: int = 7, sim_threshold: float = 0.85):
        self.time_window = timedelta(days=time_window_days)
        self.sim_threshold = sim_threshold
        self.embeddings_model = init_embeddings()
        
    async def cluster_events(self, events: List[EventNode]) -> List[EventCluster]:
        """Main clustering pipeline."""
        if not events:
            return []
            
        # 1. Prepare Inputs (Filter events without time)
        valid_events = [e for e in events if e.time is not None]
        if not valid_events:
            return [] # Or return unclustered? For now return empty or handle unclustered separately
            
        # 2. Batch Embeddings (descriptions + title)
        texts = [f"{e.title}: {e.description}" for e in valid_events]
        # Use async embed if available, otherwise sync. 
        # OpenAIEmbeddings langchain wrapper usually exposes embed_documents (sync) and aembed_documents (async)
        try:
            vectors_list = await self.embeddings_model.aembed_documents(texts)
        except AttributeError:
             # Fallback if async not available or run in executor
            vectors_list = self.embeddings_model.embed_documents(texts)

        # Convert to numpy for fast calc
        vectors = np.array(vectors_list)
        # Normalize vectors for dot product = cosine similarity
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # Avoid divide by zero
        norms[norms == 0] = 1e-10
        normalized_vectors = vectors / norms
        
        # 3. Build Adjacency List (Union-Find Preparation)
        n = len(valid_events)
        parent = list(range(n))
        
        def find(i):
            if parent[i] != i:
                parent[i] = find(parent[i])
            return parent[i]
            
        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_j] = root_i
                
        # 4. Pairwise Check
        # Optimization: Sort by time first to limit window check scanning?
        # For small N (<200) O(N^2) is fine. For larger, sort helps.
        # Let's simple bubble check for now, assuming N is per-topic (usually <100)
        
        for i in range(n):
            for j in range(i + 1, n):
                event_i = valid_events[i]
                event_j = valid_events[j]
                
                # Check Time
                if abs(event_i.time - event_j.time) > self.time_window:
                    continue
                    
                # Check Semantic (Dot Product)
                sim = np.dot(normalized_vectors[i], normalized_vectors[j])
                if sim >= self.sim_threshold:
                    union(i, j)
        
        # 5. Group by Component
        clusters_map: Dict[int, List[EventNode]] = {}
        for i in range(n):
            root = find(i)
            if root not in clusters_map:
                clusters_map[root] = []
            clusters_map[root].append(valid_events[i])
            
        # 6. Create EventCluster Objects
        results = []
        for root_id, cluster_events in clusters_map.items():
            # Sort by time within cluster
            cluster_events.sort(key=lambda x: x.time)
            
            # Metadata
            start = cluster_events[0].time
            end = cluster_events[-1].time
            
            # Create object
            cluster = EventCluster(
                id=f"cluster_{root_id}_{start.strftime('%Y%m%d')}",
                events=cluster_events,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                representative_title=cluster_events[0].title # Simple heuristic: first event title
            )
            results.append(cluster)
            
        # Sort clusters by start time
        results.sort(key=lambda c: c.start_date)
        
        return results
