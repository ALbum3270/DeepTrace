import os

ENV_FILE = ".env"

NEW_CONFIG = {
    "DEEPTRACE_PROXY_TUNNEL": "g282.kdltps.com:15818",
    "DEEPTRACE_PROXY_PASSWORD": "563plce7",
    "DEEPTRACE_PROXY_USERNAME": "t16493378981178",
    "DEEPTRACE_PROXY_USER_CH1": "t16493378981178",
    "DEEPTRACE_PROXY_USER_CH2": "",
    "DEEPTRACE_PROXY_USER_CH3": ""
}

def update_env():
    if not os.path.exists(ENV_FILE):
        print(f"Error: {ENV_FILE} not found!")
        return

    with open(ENV_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    updated_keys = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        
        if "=" in stripped:
            key, val = stripped.split("=", 1)
            key = key.strip()
            if key in NEW_CONFIG:
                new_lines.append(f"{key}={NEW_CONFIG[key]}\n")
                updated_keys.add(key)
                print(f"Updated {key}")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Append missing keys
    for key, val in NEW_CONFIG.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}\n")
            print(f"Added {key}")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    print("Successfully updated .env file.")

if __name__ == "__main__":
    update_env()
