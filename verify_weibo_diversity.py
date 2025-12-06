import asyncio
import os
import logging
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from src.fetchers.weibo.fetcher import WeiboFetcher
from src.config.settings import settings

# Setup logging
logging.basicConfig(level=logging.INFO)

async def main():
    # Force settings for verification
    settings.WEIBO_SEARCH_MODE = "balanced"
    settings.MAX_WEIBO_POSTS_PER_QUERY = 12
    
    print(f"--- Verifying Weibo Diversity (Mode: {settings.WEIBO_SEARCH_MODE}) ---")
    
    fetcher = WeiboFetcher(backend="mindspider")
    query = "DeepSeek" # Use a hot topic
    
    evidences = await fetcher.fetch(query)
    
    print(f"\nFetched {len(evidences)} evidences.")
    
    print("\n--- Top 5 Evidences (Check Scores) ---")
    for i, ev in enumerate(evidences[:5]):
        score = ev.metadata.get("score", 0)
        likes = ev.metadata.get("likes", 0)
        reposts = ev.metadata.get("reposts", 0)
        comments = ev.metadata.get("comments", 0)
        print(f"{i+1}. Score: {score:.2f} | Likes: {likes}, Reposts: {reposts}, Comments: {comments} | Title: {ev.title}")

    # Check if we have a mix of high score and low score (realtime)
    # Realtime posts might have low scores but be present if they are in the 'realtime' slot
    
    print("\n--- Verification Finished ---")

if __name__ == "__main__":
    asyncio.run(main())
