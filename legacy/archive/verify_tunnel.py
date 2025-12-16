import asyncio
import os
import logging
from dotenv import load_dotenv

# Load env
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_weibo_tunnel():
    logger.info("Testing Weibo Tunnel Proxy...")
    
    # Ensure env vars are loaded
    logger.info(f"Proxy Enabled: {os.getenv('DEEPTRACE_PROXY_ENABLED')}")
    logger.info(f"Tunnel: {os.getenv('DEEPTRACE_PROXY_TUNNEL')}")

    from src.fetchers.weibo.client import WeiboClient
    from src.infrastructure.utils.crawler_util import convert_str_cookie_to_dict
    
    # Load cookies
    cookie_str = os.getenv("DEEPTRACE_WEIBO_COOKIES", "")
    cookie_dict = convert_str_cookie_to_dict(cookie_str) if cookie_str else {}
    
    client = WeiboClient(cookie_dict=cookie_dict)
    
    # Test URL (User Profile Info)
    # Using a random popular UID for testing (e.g., 1669879400 - CCTV News)
    test_uid = "1669879400" 
    url = f"/ajax/profile/info?uid={test_uid}"
    
    try:
        # We need to use the full URL for the client.get method if it expects a path
        # But looking at client.get implementation:
        # return await self.request(method="GET", url=f"{self._host}{final_uri}", ...)
        # So we pass the path.
        
        # However, the user's example used "https://weibo.com/ajax/..."
        # My client._host is "https://m.weibo.cn"
        # Let's try to use the client's native host first to see if it works with tunnel.
        
        logger.info(f"Requesting {url} via m.weibo.cn...")
        data = await client.get(url, return_response=True)
        
        if hasattr(data, 'status_code'):
             logger.info(f"Status Code: {data.status_code}")
             logger.info(f"Headers: {data.headers}")
             logger.info(f"Body Preview: {data.text[:200]}")
        else:
             logger.info(f"Data: {data}")

    except Exception as e:
        logger.error(f"Tunnel test failed: {e}")

if __name__ == "__main__":
    import sys
    sys.path.append(os.getcwd())
    asyncio.run(test_weibo_tunnel())
