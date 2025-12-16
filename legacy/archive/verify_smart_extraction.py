import asyncio
import os
import logging
from dotenv import load_dotenv
from src.graph.nodes.extract_node import extract_comments_node
from src.core.models.evidence import Evidence
from src.core.models.plan import WeiboCommentDepth
from src.fetchers.weibo.client import WeiboClient

# Load env vars
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

async def verify_smart_extraction():
    # Load cookies
    cookie_str = os.getenv("DEEPTRACE_WEIBO_COOKIES", "")
    cookie_dict = {}
    if cookie_str:
        for item in cookie_str.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookie_dict[k] = v
                
    # 1. Find a popular post
    client = WeiboClient(cookie_dict=cookie_dict)
    keyword = "DeepSeek"
    print(f"Searching for popular post about '{keyword}'...")
    search_res = await client.get_note_by_keyword(keyword=keyword)
    
    cards = search_res.get("cards", [])
    target_mblog = None
    
    # Find post with comments
    for card in cards:
        if card.get("card_type") == 9:
            mblog = card.get("mblog")
            if mblog and mblog.get("comments_count", 0) > 10:
                target_mblog = mblog
                break
                
    if not target_mblog:
        print("No popular post found. Using fallback (might have few comments).")
        # Fallback to first one
        for card in cards:
             if card.get("card_type") == 9:
                target_mblog = card.get("mblog")
                break
    
    if not target_mblog:
        print("No posts found at all.")
        return

    mid = target_mblog.get("id")
    user = target_mblog.get("user", {}).get("screen_name", "Unknown")
    print(f"Target Post: [{mid}] by {user}, Comments: {target_mblog.get('comments_count')}")
    
    # 2. Construct Mock State
    evidence = Evidence(
        url=f"https://m.weibo.cn/detail/{mid}",
        content="Mock content",
        source_type="weibo",
        metadata={"platform": "weibo", "mblog": target_mblog}
    )
    
    # Test "Deep" mode
    depth_config = WeiboCommentDepth(mode="deep", suggested_max_comments=50)
    state = {
        "evidences": [evidence],
        "weibo_comment_depth": depth_config
    }
    
    print("\nRunning ExtractNode with mode='deep' (limit=50)...")
    result = await extract_comments_node(state)
    
    comments = result.get("comments", [])
    print(f"\nExtracted {len(comments)} comments.")
    for i, c in enumerate(comments[:5], 1):
        print(f"[{i}] {c.author}: {c.content[:30]}...")

if __name__ == "__main__":
    asyncio.run(verify_smart_extraction())
