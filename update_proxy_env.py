
import os

env_path = ".env"

# Read existing content
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
else:
    # This shouldn't happen as we just wrote it, but fail safe
    lines = []

updated_lines = []
# Keys to update
keys_to_update = {
    "DEEPTRACE_PROXY_KDL_SECRET_ID": "obfrhigx7oajum5j9e9u",
    "DEEPTRACE_PROXY_KDL_SIGNATURE": "3rpzo4u82h9dpkdkfvjskydcq3x5ou8f"
}
# Keep previous updates
keys_to_update["DEEPTRACE_PROXY_KDL_USER_NAME"] = "d1010886860" 
keys_to_update["DEEPTRACE_PROXY_KDL_USER_PWD"] = "zwhxcg60"

found_keys = set()

for line in lines:
    key_found = False
    for k, v in keys_to_update.items():
        if line.startswith(f"{k}="):
            updated_lines.append(f"{k}={v}\n")
            found_keys.add(k)
            key_found = True
            break
    if not key_found:
        updated_lines.append(line)

# Append missing
for k, v in keys_to_update.items():
    if k not in found_keys:
        updated_lines.append(f"{k}={v}\n")

with open(env_path, "w", encoding="utf-8") as f:
    f.writelines(updated_lines)

print("Updated .env with API SecretID and Signature.")
