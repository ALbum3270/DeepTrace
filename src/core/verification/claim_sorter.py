"""
Claim Sorting & Verification Module (Contract 4 Enforcer).
Implements logic to split Verified vs Disputed claims based on Source Independence.
"""
import numpy as np
from typing import List, Dict, Tuple, Set
from urllib.parse import urlparse
from pydantic import BaseModel

from ..models.claim import Claim
from ..models.evidence import Evidence
from ...llm.factory import init_embeddings

class SourceClusterer:
    """
    Groups Evidence into Source Clusters to detect syndication.
    Rule:
    1. Same Domain -> Same Cluster.
    2. Different Domain but High Content Similarity (>0.95) -> Same Cluster (Syndication).
    """
    def __init__(self, sim_threshold: float = 0.95):
        self.sim_threshold = sim_threshold
        self.embeddings_model = init_embeddings()

    async def cluster_sources(self, evidences: List[Evidence]) -> Dict[str, str]:
        """
        Returns a mapping: evidence_id -> source_cluster_id
        """
        if not evidences:
            return {}

        # 1. Initial Grouping by Domain
        domain_groups: Dict[str, List[Evidence]] = {}
        for ev in evidences:
            domain = self._extract_domain(ev.url)
            if domain not in domain_groups:
                domain_groups[domain] = []
            domain_groups[domain].append(ev)

        # 2. Assign Initial Cluster IDs (by Domain)
        # ev_id -> cluster_id
        cluster_map: Dict[str, str] = {}
        # Keep track of representative embedding for each cluster
        cluster_embeddings: Dict[str, np.ndarray] = {} 
        
        # Prepare embeddings needed?
        # Only if we suspect syndication. 
        # Strategy: Embed ALL items.
        # Merge clusters if their representatives are too similar.
        
        texts = [(ev.title or "") + " " + ev.content[:500] for ev in evidences]
        try:
            vectors_list = await self.embeddings_model.aembed_documents(texts)
        except AttributeError:
            vectors_list = self.embeddings_model.embed_documents(texts)
        
        vectors = np.array(vectors_list)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        norm_vectors = vectors / norms
        
        # Map ev_id to vector index
        ev_idx_map = {ev.id: i for i, ev in enumerate(evidences)}

        # Union-Find for Cluster Merging
        # Nodes are Domains.
        domains = list(domain_groups.keys())
        parent = {d: d for d in domains}

        def find(d):
            if parent[d] != d:
                parent[d] = find(parent[d])
            return parent[d]

        def union(d1, d2):
            root1 = find(d1)
            root2 = find(d2)
            if root1 != root2:
                parent[root2] = root1
        
        # Compute "Domain Representative Vector" (Average of items in domain)
        domain_vectors = {}
        for domain, ev_list in domain_groups.items():
            indices = [ev_idx_map[ev.id] for ev in ev_list]
            # Average vector
            avg_vec = np.mean(norm_vectors[indices], axis=0)
            # Re-normalize
            n = np.linalg.norm(avg_vec)
            if n > 0:
                avg_vec = avg_vec / n
            domain_vectors[domain] = avg_vec

        # Allow O(D^2) check where D is number of domains (usually small, <20)
        d_keys = list(domain_vectors.keys())
        for i in range(len(d_keys)):
            for j in range(i + 1, len(d_keys)):
                d1 = d_keys[i]
                d2 = d_keys[j]
                
                # Check Similarity
                sim = np.dot(domain_vectors[d1], domain_vectors[d2])
                if sim > self.sim_threshold:
                    union(d1, d2)

        # Build Final Map
        for ev in evidences:
            domain = self._extract_domain(ev.url)
            root_domain = find(domain)
            cluster_map[ev.id] = f"cluster_{root_domain}"
            
        return cluster_map

    def _extract_domain(self, url: str) -> str:
        if not url:
            return "unknown_source"
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc
            # Simple domain extraction (e.g. www.google.com -> google.com)
            parts = netloc.split('.')
            if len(parts) > 2:
                return ".".join(parts[-2:])
            return netloc
        except Exception:
            return "invalid_url"


class ClaimSorter:
    """
    Sorts claims into Verified vs Disputed based on supporting evidence clusters.
    """
    def __init__(self, source_clusterer: SourceClusterer):
        self.clusterer = source_clusterer

    async def sort_claims(self, claims: List[Claim], evidences: List[Evidence]) -> Tuple[List[Claim], List[Claim]]:
        """
        Process:
        1. Cluster Evidence sources.
        2. For each claim, count distinct source clusters.
        3. If distinct_clusters >= 2 -> Verified.
        4. Else -> Disputed (or Unverified).
        """
        if not claims:
            return [], []

        # 1. Cluster Sources
        ev_cluster_map = await self.clusterer.cluster_sources(evidences)
        
        # Map ev_id -> Evidence object for lookups
        ev_map = {ev.id: ev for ev in evidences}
        
        verified = []
        disputed = []
        
        for claim in claims:
            # 2. Get supporting evidence IDs
            # Assuming claim.supporting_evidence_ids is populated (Phase 16)
            # Use source_evidence_id as fallback if list empty
            support_ids = set(claim.supporting_evidence_ids)
            if claim.source_evidence_id:
                support_ids.add(claim.source_evidence_id)
            
            # 3. Count distinct source clusters
            found_clusters = set()
            for eid in support_ids:
                if eid in ev_cluster_map:
                    found_clusters.add(ev_cluster_map[eid])
            
            # 4. Verification Logic (Contract 4)
            distinct_count = len(found_clusters)
            
            if distinct_count >= 2:
                claim.status = "verified"
                # Logic: Is it Disputed? Disputed implies conflict.
                # If verified but has conflict flag -> disputed
                # For now use Contract 4 basic rule: >=2 independent sources = Verified Candidate
                # If already marked disputed by LLM, keep it disputed? 
                # Let's enforce the "Verified" status upgrade if checks pass
                # But if there are internal conflicts, the Director handles it.
                # Here we just mark verification level.
                verified.append(claim)
            else:
                claim.status = "disputed" # Or unverified. Spec says "Disputed" list.
                disputed.append(claim)
                
        return verified, disputed
