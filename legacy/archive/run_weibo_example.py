import asyncio
import logging
import os
from dotenv import load_dotenv
from src.fetchers.weibo.fetcher import WeiboFetcher

# Load env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_example():
    logger.info("Initializing WeiboFetcher with MindSpider backend...")
    fetcher = WeiboFetcher(backend="mindspider")
    
    query = "DeepSeek"
    logger.info(f"Fetching Weibo content for query: '{query}'...")
    
    try:
        evidences = await fetcher.fetch(query)
        
        logger.info(f"Successfully fetched {len(evidences)} items.")
        
        print("\n" + "="*50)
        print(f"Results for '{query}':")
        print("="*50)
        
        for i, ev in enumerate(evidences, 1):
            print(f"\n[{i}] {ev.title}")
            print(f"Author: {ev.metadata.get('author', 'Unknown')}")
            print(f"Time: {ev.metadata.get('publish_time', 'Unknown')}")
            print(f"URL: {ev.url}")
            print(f"Content Snippet: {ev.content[:100]}...")
            print("-" * 30)
            
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")

if __name__ == "__main__":
    asyncio.run(run_example())
