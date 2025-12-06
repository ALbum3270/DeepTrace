import os
import random
from typing import Optional, Dict, Union

def load_proxies() -> Optional[Dict[str, str]]:
    """
    Legacy wrapper for backward compatibility.
    Defaults to Channel 3 (Per-request rotation) or falls back to basic config.
    """
    return build_proxies_for_channel(ch=3)

def build_proxies_for_channel(ch: Optional[int] = None) -> Optional[Dict[str, str]]:
    """
    Build proxy configuration for a specific channel.
    ch=1: 5-min rotation A
    ch=2: 5-min rotation B
    ch=3: Per-request rotation
    ch=None: Random channel
    """
    tunnel = os.getenv("DEEPTRACE_PROXY_TUNNEL")
    password = os.getenv("DEEPTRACE_PROXY_PASSWORD")
    
    if not (tunnel and password):
        # Fallback to legacy env vars if new ones aren't set
        http = os.getenv("DEEPTRACE_PROXY_HTTP")
        if http:
             return {"http://": http, "https://": http} # httpx format
        return None

    users = [
        os.getenv("DEEPTRACE_PROXY_USER_CH1"),
        os.getenv("DEEPTRACE_PROXY_USER_CH2"),
        os.getenv("DEEPTRACE_PROXY_USER_CH3"),
    ]
    # Filter out None values
    valid_users = [u for u in users if u]

    if not valid_users:
        # Fallback if channels aren't defined but tunnel is
        username = os.getenv("DEEPTRACE_PROXY_USERNAME")
        if username:
             proxy_url = f"http://{username}:{password}@{tunnel}/"
             return {"http://": proxy_url, "https://": proxy_url}
        return None

    if ch is None:
        username = random.choice(valid_users)
    else:
        # Map 1-based index to 0-based list
        idx = max(0, min(ch - 1, len(valid_users) - 1))
        username = valid_users[idx]

    proxy_url = f"http://{username}:{password}@{tunnel}/"
    
    # Return in httpx format (keys with '://')
    return {
        "http://": proxy_url,
        "https://": proxy_url
    }
