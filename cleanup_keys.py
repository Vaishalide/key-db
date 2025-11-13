import json
import requests
import base64
from datetime import datetime
import pytz

# --- CONFIGURATION (Copy these from your api.py) ---
GITHUB_REPO_OWNER = "Vaishalide"
GITHUB_REPO_NAME = "Key-DB"
GITHUB_ACCESS_TOKEN = "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"
IST = pytz.timezone('Asia/Kolkata')

# --- HELPER FUNCTIONS (Copy these from your api.py) ---
def get_github_keys_file_url():
    return f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/keys.json"

def get_github_keys_content():
    url = get_github_keys_file_url()
    headers = {
    "Authorization": f"token {GITHUB_ACCESS_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    # --- Add these lines to prevent caching ---
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json()["content"]
            return json.loads(base64.b64decode(content).decode("utf-8")), response.json()["sha"]
        return {}, None
    except:
        return {}, None

def save_to_github(data, sha):
    url = get_github_keys_file_url()
    headers = {
        "Authorization": f"token {GITHUB_ACCESS_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "message": "Automated cleanup of expired keys",
        "content": base64.b64encode(json.dumps(data, indent=2).encode("utf-8")).decode("utf-8"),
        "sha": sha
    }
    try:
        response = requests.put(url, headers=headers, json=payload)
        return response.status_code in (200, 201)
    except:
        return False

# --- MAIN CLEANUP LOGIC ---
def cleanup_expired_keys():
    print("Starting cleanup process...")
    keys_data, sha = get_github_keys_content()
    if not keys_data:
        print("No keys found or failed to fetch file. Exiting.")
        return

    original_key_count = len(keys_data)
    current_time = datetime.now(IST)
    
    # Create a new dictionary with only the valid (non-expired) keys
    valid_keys = {}
    for user_id, data in keys_data.items():
        try:
            expiry_time = datetime.fromisoformat(data["expiry_time"])
            if current_time <= expiry_time:
                valid_keys[user_id] = data
        except (ValueError, KeyError):
            # If expiry_time is missing or malformed, keep the entry
            valid_keys[user_id] = data

    removed_key_count = original_key_count - len(valid_keys)

    if removed_key_count > 0:
        print(f"Found {original_key_count} total keys. Removing {removed_key_count} expired keys.")
        if save_to_github(valid_keys, sha):
            print("Successfully removed expired keys and updated keys.json.")
        else:
            print("Error: Failed to save the updated keys.json to GitHub.")
    else:
        print(f"Found {original_key_count} total keys. No expired keys to remove.")
    
    print("Cleanup process finished.")

if __name__ == '__main__':
    cleanup_expired_keys()
