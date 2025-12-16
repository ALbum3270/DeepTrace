import asyncio
import json
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.core.models.evidence import Evidence
from src.agents.comment_extractor import extract_comments_from_article
from src.agents.comment_triage import triage_comments
from src.core.models.comments import Comment

async def main():
    # Mock evidence for verification
    target_evidence = Evidence(
        id="mock_ev_1",
        title="Sora Release Controversy",
        content="Summary of Sora release.",
        full_content="""
        OpenAI released Sora yesterday, causing a huge stir.
        
        "This is a game changer for the film industry," said Sam Altman, CEO of OpenAI.
        
        However, social media users are divided. On Weibo, user @TechGuru commented: "The generated videos are too realistic, it's scary."
        Another user @ArtistLife wrote: "This might kill entry-level animation jobs."
        
        Critics argue that the training data might infringe on copyright.
        """,
        url="http://example.com/sora",
        source="news",
        type="article"
    )

    print(f"Found evidence: {target_evidence.title} ({target_evidence.url})")
    print(f"Full content length: {len(target_evidence.full_content)}")
    print(f"Content preview: {target_evidence.full_content}")
    
    # 1. Extract
    print("\n--- Extracting Comments ---")
    comments = await extract_comments_from_article(target_evidence)
    print(f"Extracted {len(comments)} comments.")
    for c in comments:
        print(f"  - [{c.role}] {c.author}: {c.content[:50]}...")
        
    if not comments:
        print("Extraction returned empty.")
        return

    # 2. Triage
    print("\n--- Triaging Comments ---")
    scores = await triage_comments(target_evidence, comments)
    for s in scores:
        print(f"  - Score: {s.total_score:.2f} (Novelty: {s.novelty}, Evidence: {s.evidence})")
        if s.total_score >= 0.7: # Assuming 0.7 threshold
            print("    -> PROMOTED")
        else:
            print("    -> REJECTED")

if __name__ == "__main__":
    asyncio.run(main())
