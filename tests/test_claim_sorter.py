
import pytest
import numpy as np
from typing import List
from src.core.models.evidence import Evidence
from src.core.models.claim import Claim
from src.core.verification.claim_sorter import ClaimSorter, SourceClusterer

# Mock Embeddings
class MockEmbeddings:
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Mock strategy: 
        # "Syndicated News" -> [1.0, 0.0]
        # "Independent Blog" -> [0.0, 1.0]
        vectors = []
        for text in texts:
            if "Syndicated" in text:
                vectors.append([1.0, 0.0])
            elif "Independent" in text:
                vectors.append([0.0, 1.0])
            else:
                # Random noise
                vectors.append([0.5, 0.5]) 
        return vectors
        
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed_documents(texts)

@pytest.mark.asyncio
async def test_claim_verification_contract4():
    """测试 Contract 4: Source Independence"""
    
    # Setup Evidence
    # 1. Cluster A (Synicated): 3 evidences from diff domains but same text
    ev1 = Evidence(
        id="e1", content="Syndicated News: Big Event happened.", 
        url="http://news.yahoo.com/a", title="News A"
    )
    ev2 = Evidence(
        id="e2", content="Syndicated News: Big Event happened.", 
        url="http://news.msn.com/b", title="News B"
    )
    # 2. Cluster B (Independent): 1 evidence
    ev3 = Evidence(
        id="e3", content="Independent Blog: Another view.", 
        url="http://blog.independent.com/c", title="Blog C"
    )
    
    evidences = [ev1, ev2, ev3]
    
    # Setup Sorter & Mock
    clusterer = SourceClusterer(sim_threshold=0.9)
    clusterer.embeddings_model = MockEmbeddings()
    sorter = ClaimSorter(clusterer)
    
    # Test Case 1: Claim supported by ev1, ev2 (Same Cluster)
    # Expected: Disputed/Unverified (Count = 1)
    c1 = Claim(
        content="Big Event happened", 
        source_evidence_id="e1",
        supporting_evidence_ids=["e2"],
        credibility_score=80.0, importance=80.0
    )
    
    # Test Case 2: Claim supported by ev1, ev3 (Diff Clusters)
    # Expected: Verified (Count = 2)
    c2 = Claim(
        content="Something happened", 
        source_evidence_id="e1",
        supporting_evidence_ids=["e3"],
        credibility_score=80.0, importance=80.0
    )
    
    verified, disputed = await sorter.sort_claims([c1, c2], evidences)
    
    # Assertions
    # Claim 1 should be in disputed/unverified list (technically 'disputed' by our logic)
    assert c1.status == "disputed"
    assert c1 in disputed
    
    # Claim 2 should be verified
    assert c2.status == "verified"
    assert c2 in verified

@pytest.mark.asyncio
async def test_domain_extraction():
    clusterer = SourceClusterer()
    assert clusterer._extract_domain("https://www.google.com/news") == "google.com"
    assert clusterer._extract_domain("http://cn.nytimes.com/zh") == "nytimes.com"
