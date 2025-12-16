import asyncio
import os
import logging
from dotenv import load_dotenv
from src.fetchers.weibo.client import WeiboClient

# Load env vars
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_comments():
    # Load cookies
    cookie_str = os.getenv("DEEPTRACE_WEIBO_COOKIES", "")
    cookie_dict = {}
    if cookie_str:
        for item in cookie_str.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookie_dict[k] = v
                
    client = WeiboClient(cookie_dict=cookie_dict)
    
    # 1. Search for a post to get an ID
    keyword = "DeepSeek"
    print(f"Searching for '{keyword}'...")
    search_res = await client.get_note_by_keyword(keyword=keyword)
    
    cards = search_res.get("cards", [])
    target_mblog = None
    
    for card in cards:
        if card.get("card_type") == 9:
            mblog = card.get("mblog")
            if mblog:
                target_mblog = mblog
                break
                
    if not target_mblog:
        print("No posts found.")
        return

    mid = target_mblog.get("id")
    user = target_mblog.get("user", {}).get("screen_name", "Unknown")
    text = target_mblog.get("text", "")[:50]
    print(f"\nFound Post: [{mid}] by {user}")
    print(f"Content: {text}...")
    
    # 2. Fetch Comments via API
    print(f"\nFetching comments for {mid}...")
    try:
        # First page: max_id=0
        comments_data = await client.get_note_comments(mid_id=mid, max_id=0)
        
        # Client returns data['data'] if success, or full response if warning
        # If it's a list or dict without 'ok', it's likely success data
        first_page_data = None
        if isinstance(comments_data, dict) and "ok" not in comments_data:
            first_page_data = comments_data
        elif comments_data.get("ok") == 1:
            first_page_data = comments_data.get("data", {})

        if first_page_data:
            comments = first_page_data.get("data", [])
            max_id = first_page_data.get("max_id", 0)
            max_id_type = first_page_data.get("max_id_type", 0)
            
            print(f"Page 1: Fetched {len(comments)} comments. Next max_id: {max_id}")
            for i, c in enumerate(comments[:3], 1):
                user = c.get("user", {}).get("screen_name", "Unknown")
                content = c.get("text", "")
                print(f"  [{i}] {user}: {content[:30]}...")

            # Fetch Page 2 if max_id exists
            if max_id and max_id != 0:
                print(f"\nFetching Page 2 (max_id={max_id})...")
                await asyncio.sleep(2) # Polite delay
                page2_res = await client.get_note_comments(mid_id=mid, max_id=max_id, max_id_type=max_id_type)
                
                page2_data = None
                if isinstance(page2_res, dict) and "ok" not in page2_res:
                    page2_data = page2_res
                elif page2_res.get("ok") == 1:
                    page2_data = page2_res.get("data", {})
                    
                if page2_data:
                    p2_comments = page2_data.get("data", [])
                    print(f"Page 2: Fetched {len(p2_comments)} comments!")
                    for i, c in enumerate(p2_comments[:3], 1):
                        user = c.get("user", {}).get("screen_name", "Unknown")
                        content = c.get("text", "")
                        print(f"  [{i}] {user}: {content[:30]}...")
                else:
                    print(f"Page 2 fetch failed: {page2_res}")
            else:
                print("No more pages (max_id=0).")
        else:
            print("Failed to fetch comments. Response:")
            import json
            print(json.dumps(comments_data, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Error fetching comments: {e}")

if __name__ == "__main__":
    asyncio.run(verify_comments())
