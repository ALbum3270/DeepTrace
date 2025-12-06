import asyncio
import os
import logging
from dotenv import load_dotenv

# Load env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_weibo_fetcher():
    logger.info("Testing WeiboFetcher...")
    from src.fetchers.weibo.fetcher import WeiboFetcher
    
    # Test SerpAPI Backend
    logger.info("--- Testing SerpAPI Backend ---")
    fetcher_serp = WeiboFetcher(backend="serpapi")
    try:
        results = await fetcher_serp.fetch("DeepSeek")
        logger.info(f"SerpAPI Results: {len(results)}")
        if results:
            logger.info(f"Sample: {results[0].title}")
    except Exception as e:
        logger.error(f"SerpAPI failed: {e}")

    # Test MindSpider Backend
    logger.info("--- Testing MindSpider Backend ---")
    # Only run if proxy is configured, otherwise it might fail or use direct connection (soft close)
    fetcher_mind = WeiboFetcher(backend="mindspider")
    try:
        results = await fetcher_mind.fetch("DeepSeek")
        logger.info(f"MindSpider Results: {len(results)}")
        if results:
            logger.info(f"Sample: {results[0].title}")
            logger.info(f"Metadata: {results[0].metadata}")
    except Exception as e:
        logger.error(f"MindSpider failed: {e}")

async def test_xhs_fetcher():
    logger.info("\nTesting XHSFetcher...")
    from src.fetchers.xhs.fetcher import XHSFetcher
    
    # Test SerpAPI Backend
    logger.info("--- Testing SerpAPI Backend ---")
    fetcher_serp = XHSFetcher(backend="serpapi")
    try:
        results = await fetcher_serp.fetch("DeepSeek")
        logger.info(f"SerpAPI Results: {len(results)}")
    except Exception as e:
        logger.error(f"SerpAPI failed: {e}")

    # Test MindSpider Backend
    logger.info("--- Testing MindSpider Backend ---")
    fetcher_mind = XHSFetcher(backend="mindspider")
    try:
        results = await fetcher_mind.fetch("DeepSeek")
        logger.info(f"MindSpider Results: {len(results)}")
        if results:
            logger.info(f"Sample: {results[0].title}")
            logger.info(f"Metadata: {results[0].metadata}")
    except Exception as e:
        logger.error(f"MindSpider failed: {e}")

async def main():
    await test_weibo_fetcher()
    # await test_xhs_fetcher() # XHS might need cookies/browser, run carefully

if __name__ == "__main__":
    # Adjust path to make imports work
    import sys
    sys.path.append(os.getcwd())
    asyncio.run(main())
