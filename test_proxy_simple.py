import os
from dotenv import load_dotenv

load_dotenv()

# Attempt to use specific USER/PASS from .env if available, else hardcoded fallback (which we are replacing)
KDL_USER = os.getenv("DEEPTRACE_PROXY_KDL_USER_NAME", "")
KDL_PWD = os.getenv("DEEPTRACE_PROXY_KDL_USER_PWD", "")

# Note: This test assumes Tunnel Mode (tps domain) which might not work for Private Proxy API mode.
# But we update it to use the new credentials so we can at least try or show the user we are using their inputs.
CREDENTIALS = {
    "user": KDL_USER,
    "pass": KDL_PWD,
    "host_primary": "g282.kdltps.com:15818", # Might be wrong for Private Proxy
    "host_backup": "g283.kdltps.com:15818"
}

def test_proxy(host, label):
    print(f"Testing {label}: {host}...")
    proxy_url = f"http://{CREDENTIALS['user']}:{CREDENTIALS['pass']}@{host}"
    proxies = {"http": proxy_url, "https": proxy_url}
    
    try:
        start = time.time()
        # Using baidu.com for speed in China/General connectivity, or httpbin for IP
        resp = requests.get("https://www.baidu.com", proxies=proxies, timeout=10)
        print(f"[{label}] Status: {resp.status_code}, Time: {time.time()-start:.2f}s")
        return True
    except Exception as e:
        print(f"[{label}] Failed: {str(e)[:100]}...")
        return False

if __name__ == "__main__":
    success = test_proxy(CREDENTIALS["host_primary"], "PRIMARY")
    if not success:
        print("Retrying with BACKUP...")
        test_proxy(CREDENTIALS["host_backup"], "BACKUP")
