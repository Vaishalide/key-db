import os
import json
import secrets
import requests
import base64
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template_string
import pytz
from urllib.parse import urlencode
import redis  # <-- IMPORT REDIS

app = Flask(__name__)

# --- MODIFIED: CONNECT TO REDIS & HANDLE HEROKU SSL ---
redis_url = os.environ.get('REDIS_URL')

if redis_url:
    # On Heroku, REDIS_URL is present. Connect with SSL verification disabled.
    redis_client = redis.from_url(redis_url, ssl_cert_reqs=None)
else:
    # For local development where REDIS_URL is not set.
    redis_client = redis.from_url('redis://localhost:6379')

# Configuration
GITHUB_REPO_OWNER = "Vaishalide"
GITHUB_REPO_NAME = "Key-DB"
GITHUB_ACCESS_TOKEN = "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"
TOKEN_EXPIRY_MINUTES = 30  # <-- UPDATED to 30 minutes as requested
KEY_EXPIRY_DAYS = 1
SHORTENER_API_KEY = "be1be8f8f3c02db2e943cc7199c5641971d86283"

IST = pytz.timezone('Asia/Kolkata')

def get_current_ist_time():
    return datetime.now(IST)

# --- All your GitHub and helper functions remain unchanged ---

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
            return json.loads(base64.b64decode(content).decode("utf-8"))
        return {}
    except:
        return {}

def save_to_github(data):
    url = get_github_keys_file_url()
    headers = {
        "Authorization": f"token {GITHUB_ACCESS_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    sha = None
    try:
        existing_response = requests.get(url, headers=headers)
        if existing_response.status_code == 200:
            sha = existing_response.json()["sha"]
    except:
        pass
    data = {
        "message": "Update keys.json",
        "content": base64.b64encode(json.dumps(data, indent=2).encode("utf-8")).decode("utf-8"),
        "sha": sha
    }
    try:
        response = requests.put(url, headers=headers, json=data)
        return response.status_code in (200, 201)
    except:
        return False

def generate_token():
    return secrets.token_hex(16)

def generate_key():
    return secrets.token_hex(12)

def shorten_url(long_url):
    try:
        random_suffix = secrets.token_hex(3)[:6]
        alias = f"RDTHXXX{random_suffix}"
        shortener_url = (
            f"https://api.gplinks.com/api?api={SHORTENER_API_KEY}"
            f"&url={requests.utils.quote(long_url)}"
            f"&alias={alias}"
        )
        response = requests.get(shortener_url)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error shortening URL: {e}")
        return None

# --- DELETED the old in-memory dictionary: `temporary_tokens = {}` ---

@app.route('/api/login', methods=['GET'])
def login():
    user_id = request.args.get('id')
    if not user_id:
        return jsonify({"status": "error", "message": "ID is required"}), 400

    token = generate_token()

    # --- MODIFIED: Save token to Redis with an automatic expiry ---
    token_data = json.dumps({"user_id": user_id})
    redis_client.setex(token, timedelta(minutes=TOKEN_EXPIRY_MINUTES), token_data)

    verify_url = f"{request.url_root}api/verify?token={token}&id={user_id}"

    short_url_data = shorten_url(verify_url)
    if not short_url_data:
        return jsonify({"status": "error", "message": "Failed to shorten URL"}), 500

    response_data = {
        "status": "success",
        "shortenedUrl": short_url_data.get("shortenedUrl"),
        "video_url": "https://youtube.com/shorts/a9jf4pOVTXw?si=5Pq1G20M_iAv0Rnc"
    }
    return jsonify(response_data)

@app.route('/api/verify', methods=['GET'])
def verify():
    query_string = request.query_string.decode()
    token = None
    user_id = None
    if '&id=' in query_string:
        token = request.args.get('token')
        user_id = request.args.get('id')
    elif '&amp;id=' in query_string:
        parts = query_string.split('&amp;id=')
        if len(parts) == 2:
            token = parts[0].replace('token=', '')
            user_id = parts[1]
    
    if not token or not user_id:
        return "Invalid request", 400

    # --- MODIFIED: Check for token in Redis ---
    token_data_from_redis = redis_client.get(token)

    if not token_data_from_redis:
        # If the token is not in Redis, it's either invalid or has expired
        return "Invalid or expired token", 400

    stored_data = json.loads(token_data_from_redis.decode('utf-8'))
    stored_user_id = stored_data.get('user_id')

    if stored_user_id != user_id:
        return "Invalid or expired token", 400

    # --- The rest of your logic is unchanged ---
    current_time = get_current_ist_time()
    keys_data = get_github_keys_content()

    if user_id in keys_data:
        key_data = keys_data[user_id]
        expiry_time = datetime.fromisoformat(key_data["expiry_time"])
        if current_time <= expiry_time:
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Your Authentication Key</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
                <style>
                    :root{--primary:#4361ee;--primary-dark:#3a56d4;--text:#2b2d42;--light:#f8f9fa;--success:#4cc9f0;--border-radius:12px;--box-shadow:0 10px 30px rgba(0,0,0,.08)}*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Inter',sans-serif;background-color:#f5f7ff;color:var(--text);display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;line-height:1.6}.key-container{background:#fff;border-radius:var(--border-radius);box-shadow:var(--box-shadow);width:100%;max-width:500px;padding:40px;text-align:center;position:relative;overflow:hidden}.key-container::before{content:'';position:absolute;top:0;left:0;width:100%;height:6px;background:linear-gradient(90deg,#4361ee,#4cc9f0)}.key-icon{font-size:48px;color:var(--primary);margin-bottom:20px;animation:float 3s ease-in-out infinite}h1{font-size:24px;font-weight:600;margin-bottom:15px;color:var(--text)}.key-description{color:#6c757d;margin-bottom:30px;font-size:15px}.key-input-group{position:relative;margin-bottom:25px}.key-input{width:100%;padding:15px 20px;font-size:16px;border:2px solid #e9ecef;border-radius:var(--border-radius);background:var(--light);font-family:'Courier New',monospace;font-weight:600;color:var(--text);letter-spacing:1px;transition:all .3s ease}.key-input:focus{outline:0;border-color:var(--primary);box-shadow:0 0 0 3px rgba(67,97,238,.2)}.copy-btn{background-color:var(--primary);color:#fff;border:none;padding:14px 28px;font-size:16px;font-weight:500;border-radius:var(--border-radius);cursor:pointer;transition:all .3s ease;width:100%;display:flex;align-items:center;justify-content:center;gap:8px}.copy-btn:hover{background-color:var(--primary-dark);transform:translateY(-2px)}.copy-btn:active{transform:translateY(0)}.key-meta{margin-top:25px;font-size:13px;color:#adb5bd;display:flex;justify-content:center;gap:15px}@keyframes float{0%{transform:translateY(0)}50%{transform:translateY(-8px)}100%{transform:translateY(0)}}.notification{position:fixed;top:20px;right:20px;background:#4bb543;color:#fff;padding:15px 25px;border-radius:var(--border-radius);box-shadow:var(--box-shadow);transform:translateX(150%);transition:transform .3s ease;z-index:1000;display:flex;align-items:center;gap:10px}.notification.show{transform:translateX(0)}@media (max-width:600px){.key-container{padding:30px 20px}h1{font-size:20px}}
                </style>
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            </head>
            <body>
                <div class="key-container">
                    <div class="key-icon"><i class="fas fa-key"></i></div>
                    <h1>Your Authentication Key</h1>
                    <p class="key-description">This key provides secure access to your account. Keep it confidential.</p>
                    <div class="key-input-group"><input type="text" id="keyBox" class="key-input" value="{{ key }}" readonly></div>
                    <a href="https://pwthor.site/pw.php" target="_blank" class="copy-btn" style="background-color: #28a745; text-decoration: none; margin-bottom: 10px;">
    Click Here to Go to Site
</a>

<button class="copy-btn" onclick="copyKey()">
    <i class="far fa-copy"></i> Copy Key
</button>
                    <div class="key-meta"><span><i class="far fa-clock"></i> Valid for 1 days</span><span><i class="fas fa-shield-alt"></i> Secure connection</span></div>
                </div>
                <div class="notification" id="notification"><i class="fas fa-check-circle"></i><span>Key copied to clipboard!</span></div>
                <script>
                    function copyKey(){var e=document.getElementById("keyBox");e.select(),e.setSelectionRange(0,99999),document.execCommand("copy");var o=document.getElementById("notification");o.classList.add("show"),setTimeout(function(){o.classList.remove("show")},3e3)}document.getElementById("keyBox").addEventListener("click",function(){this.select()});
                </script>
            </body>
            </html>
            ''', key=key_data["key"])

    key = generate_key()
    expiry_time = current_time + timedelta(days=KEY_EXPIRY_DAYS)
    keys_data[user_id] = {"key": key, "expiry_time": expiry_time.isoformat()}
    if not save_to_github(keys_data):
        return "Failed to save key", 500

    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Your Authentication Key</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root{--primary:#4361ee;--primary-dark:#3a56d4;--text:#2b2d42;--light:#f8f9fa;--success:#4cc9f0;--border-radius:12px;--box-shadow:0 10px 30px rgba(0,0,0,.08)}*{margin:0;padding:0;box-sizing:border-box}body{font-family:'Inter',sans-serif;background-color:#f5f7ff;color:var(--text);display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;line-height:1.6}.key-container{background:#fff;border-radius:var(--border-radius);box-shadow:var(--box-shadow);width:100%;max-width:500px;padding:40px;text-align:center;position:relative;overflow:hidden}.key-container::before{content:'';position:absolute;top:0;left:0;width:100%;height:6px;background:linear-gradient(90deg,#4361ee,#4cc9f0)}.key-icon{font-size:48px;color:var(--primary);margin-bottom:20px;animation:float 3s ease-in-out infinite}h1{font-size:24px;font-weight:600;margin-bottom:15px;color:var(--text)}.key-description{color:#6c757d;margin-bottom:30px;font-size:15px}.key-input-group{position:relative;margin-bottom:25px}.key-input{width:100%;padding:15px 20px;font-size:16px;border:2px solid #e9ecef;border-radius:var(--border-radius);background:var(--light);font-family:'Courier New',monospace;font-weight:600;color:var(--text);letter-spacing:1px;transition:all .3s ease}.key-input:focus{outline:0;border-color:var(--primary);box-shadow:0 0 0 3px rgba(67,97,238,.2)}.copy-btn{background-color:var(--primary);color:#fff;border:none;padding:14px 28px;font-size:16px;font-weight:500;border-radius:var(--border-radius);cursor:pointer;transition:all .3s ease;width:100%;display:flex;align-items:center;justify-content:center;gap:8px}.copy-btn:hover{background-color:var(--primary-dark);transform:translateY(-2px)}.copy-btn:active{transform:translateY(0)}.key-meta{margin-top:25px;font-size:13px;color:#adb5bd;display:flex;justify-content:center;gap:15px}@keyframes float{0%{transform:translateY(0)}50%{transform:translateY(-8px)}100%{transform:translateY(0)}}.notification{position:fixed;top:20px;right:20px;background:#4bb543;color:#fff;padding:15px 25px;border-radius:var(--border-radius);box-shadow:var(--box-shadow);transform:translateX(150%);transition:transform .3s ease;z-index:1000;display:flex;align-items:center;gap:10px}.notification.show{transform:translateX(0)}@media (max-width:600px){.key-container{padding:30px 20px}h1{font-size:20px}}
        </style>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </head>
    <body>
        <div class="key-container">
            <div class="key-icon"><i class="fas fa-key"></i></div>
            <h1>Your Authentication Key</h1>
            <p class="key-description">This key provides secure access to your account. Keep it confidential.</p>
            <div class="key-input-group"><input type="text" id="keyBox" class="key-input" value="{{ key }}" readonly></div>
            <a href="https://pwthor.site/pw.php" target="_blank" class="copy-btn" style="background-color: #28a745; text-decoration: none; margin-bottom: 10px;">
    Click Here to Go to Site
</a>

<button class="copy-btn" onclick="copyKey()">
    <i class="far fa-copy"></i> Copy Key
</button>
            <div class="key-meta"><span><i class="far fa-clock"></i> Valid for 1 days</span><span><i class="fas fa-shield-alt"></i> Secure connection</span></div>
        </div>
        <div class="notification" id="notification"><i class="fas fa-check-circle"></i><span>Key copied to clipboard!</span></div>
        <script>
            function copyKey(){var e=document.getElementById("keyBox");e.select(),e.setSelectionRange(0,99999),document.execCommand("copy");var o=document.getElementById("notification");o.classList.add("show"),setTimeout(function(){o.classList.remove("show")},3e3)}document.getElementById("keyBox").addEventListener("click",function(){this.select()});
        </script>
    </body>
    </html>
    ''', key=key)

@app.route('/api/check', methods=['GET'])
def check():
    user_id = request.args.get('id')
    key = request.args.get('key')
    if not user_id or not key:
        return jsonify({"status": "unauthorized"}), 400
    keys_data = get_github_keys_content()
    user_data = keys_data.get(user_id)
    if user_data and user_data["key"] == key:
        expiry_time = datetime.fromisoformat(user_data["expiry_time"])
        current_time = get_current_ist_time()
        if current_time <= expiry_time:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "unauthorized"}), 401
    else:
        return jsonify({"status": "unauthorized"}), 401

@app.route('/api/pwthor', methods=['GET'])
def admin():
    admin_key = request.args.get('adminkey')
    user_id = request.args.get('id')
    key = request.args.get('key')
    if admin_key != "ron@1234abcXYZ":
        return jsonify({"status": "error", "message": "Invalid admin key"}), 403
    if not user_id or not key:
        return jsonify({"status": "error", "message": "ID and key are required"}), 400
    expiry_time = get_current_ist_time() + timedelta(days=KEY_EXPIRY_DAYS)
    keys_data = get_github_keys_content()
    keys_data[user_id] = {
        "key": key,
        "expiry_time": expiry_time.isoformat()
    }
    if save_to_github(keys_data):
        return jsonify({"status": "success", "message": "Key added/updated"})
    else:
        return jsonify({"status": "error", "message": "Failed to save key"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
