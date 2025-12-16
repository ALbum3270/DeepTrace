import requests
import time
import os
from dotenv import load_dotenv

# Load env to get base credentials (password/host)
load_dotenv()

def test_period5_channel():
    print("Testing Kuaidaili Period-5 Channel (5-minute IP rotation)...")
    
    tunnel = os.getenv("DEEPTRACE_PROXY_TUNNEL")
    password = os.getenv("DEEPTRACE_PROXY_PASSWORD")
    
    if not (tunnel and password):
        print("Error: Base proxy config missing in .env")
        return

    # Channel 1: 5-minute rotation
    # Using the username provided in the user request
    user_ch1 = "t16482944648715-period-5-sid-aa0001"

    proxy_url = f"http://{user_ch1}:{password}@{tunnel}/"
    proxies = {
        "http":  proxy_url,
        "https": proxy_url,
    }

    url = "https://dev.kdlapi.com/testproxy"
    
    print(f"Using Channel User: {user_ch1}")
    print("-" * 30)

    last_ip = None
    
    for i in range(3):
        try:
            start_time = time.time()
            r = requests.get(url, proxies=proxies, timeout=10)
            elapsed = time.time() - start_time
            
            if r.status_code == 200:
                # The response body usually contains "client ip: xxx.xxx.xxx.xxx" or similar
                # dev.kdlapi.com/testproxy returns detailed info
                print(f"Request {i+1}: {r.text.strip().splitlines()[0]} (Time: {elapsed:.2f}s)")
                
                # Check if IP changed
                current_ip = r.text
                if last_ip and current_ip != last_ip:
                    print("  [!] IP Changed! (Unexpected for period-5 channel within short time)")
                elif last_ip:
                    print("  [OK] IP Stable.")
                last_ip = current_ip
                
            else:
                print(f"Request {i+1}: Failed with status {r.status_code}")
                
        except Exception as e:
            print(f"Request {i+1}: Error - {e}")
            
        if i < 2:
            print("Waiting 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    test_period5_channel()
