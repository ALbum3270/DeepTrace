import requests
import os
import time
from dotenv import load_dotenv

# Load env
load_dotenv()

def verify_proxy_rotation():
    print("Verifying Proxy Rotation...")
    
    tunnel_host = os.getenv("DEEPTRACE_PROXY_TUNNEL")
    username = os.getenv("DEEPTRACE_PROXY_USERNAME")
    password = os.getenv("DEEPTRACE_PROXY_PASSWORD")
    
    if not all([tunnel_host, username, password]):
        print("Error: Proxy config missing in .env")
        return

    proxy_url = f"http://{username}:{password}@{tunnel_host}"
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }
    
    target_url = "https://httpbin.org/ip"
    
    print(f"Tunnel: {tunnel_host}")
    print("-" * 30)
    
    for i in range(5):
        try:
            start_time = time.time()
            resp = requests.get(target_url, proxies=proxies, timeout=10)
            elapsed = time.time() - start_time
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"Request {i+1}: IP={data.get('origin')} (Time: {elapsed:.2f}s)")
            else:
                print(f"Request {i+1}: Failed with status {resp.status_code}")
                
        except Exception as e:
            print(f"Request {i+1}: Error - {e}")
            
        # Small delay to be nice, though tunnel supports high concurrency
        time.sleep(1)

if __name__ == "__main__":
    verify_proxy_rotation()
