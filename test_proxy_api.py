import asyncio
import logging
import requests
import time
from dotenv import load_dotenv

load_dotenv()

# Set logging level to verify internal logs of Kuaidl
logging.basicConfig(level=logging.DEBUG)

from src.infrastructure.proxy.providers.kuaidl_proxy import new_kuai_daili_proxy

async def test_api_proxy():
    print("Initializing KuaiDaiLiProxy...")
    provider = new_kuai_daili_proxy()
    print(f"Provider: {provider.kdl_user_name} / Secret: {provider.secret_id[:5]}...")
    
    try:
        print("Fetching 1 IP from API...")
        ips = await provider.get_proxy(1)
        if not ips:
            print("❌ No IPs returned from API.")
            return
        
        ip_info = ips[0]
        print(f"✅ Got IP: {ip_info.ip}:{ip_info.port} (Expire: {ip_info.expired_time_ts})")
        
        # Test Connection using this IP
        # Correctly format: http://user:pass@ip:port
        if ip_info.user and ip_info.password:
            proxy_str = f"{ip_info.user}:{ip_info.password}@{ip_info.ip}:{ip_info.port}"
        else:
            proxy_str = f"{ip_info.ip}:{ip_info.port}"
            
        print(f"Testing connection with: {proxy_str}")
        
        proxies = {
            "http": f"http://{proxy_str}",
            "https": f"http://{proxy_str}"
        }
        
        start = time.time()
        resp = requests.get("https://www.baidu.com", proxies=proxies, timeout=10)
        
        if resp.status_code == 200:
             print(f"✅ Connection Success! Status: {resp.status_code}, Time: {time.time()-start:.2f}s")
        else:
             print(f"⚠️ Connection Failed? Status: {resp.status_code}")
             
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_proxy())
