import subprocess
import json
import time
import threading
from flask import Flask, request, jsonify, Response
import requests

app = Flask(__name__)
TARGET_URL = "https://lab-evaluation-verifier-verify-463617135523.us-central1.run.app"

cached_token = None
token_expiry = 0
token_lock = threading.Lock()

def get_corp_token():
    global cached_token, token_expiry
    # Check if we have a cached token that has not expired
    if cached_token and time.time() < token_expiry:
        return cached_token

    with token_lock:
        if cached_token and time.time() < token_expiry:
            return cached_token

        try:
            out = subprocess.check_output(["gcloud", "auth", "list", "--format=json"], text=True)
            accounts = json.loads(out)
            corp_account = next((acc['account'] for acc in accounts if acc['account'].endswith('@google.com')), None)
            
            if not corp_account:
                raise Exception("No @google.com account found! Run 'gcloud auth login' with your Corp account on your Mac.")

            token = subprocess.check_output(
                ["gcloud", "auth", "print-identity-token", f"--account={corp_account}"], 
                text=True
            ).strip()
            
            cached_token = token
            # Token is valid for 1 hour; cache for 50 minutes (3000 seconds)
            token_expiry = time.time() + 3000
            print("🔑 Minted new identity token (cached for 50 minutes)")
            return token
        except Exception as e:
            raise Exception(f"Failed to get BeyondCorp token: {str(e)}")

@app.route('/evaluate', methods=['POST'])
def evaluate():
    try:
        token = get_corp_token()
    except Exception as e:
        return jsonify({"error": str(e)}), 401

    headers = {
        "Authorization": f"Bearer {token}",
        "X-User-Token": token
    }

    try:
        # Case 1: Multipart file upload
        if request.files:
            data = request.form.to_dict()
            files = {key: (file.filename, file.stream.read(), file.mimetype) for key, file in request.files.items()}
            resp = requests.post(TARGET_URL, headers=headers, data=data, files=files)

        # Case 2: JSON payload
        elif request.is_json:
            json_payload = request.get_json(silent=True) or {}
            headers["Content-Type"] = "application/json"
            resp = requests.post(TARGET_URL, headers=headers, json=json_payload)

        # Case 3: Form-data / raw fallback
        else:
            headers["Content-Type"] = request.content_type or "application/x-www-form-urlencoded"
            resp = requests.post(TARGET_URL, headers=headers, data=request.get_data())

        # If Cloud Run returns 401, invalidate cached token
        if resp.status_code == 401:
            global cached_token, token_expiry
            cached_token = None
            token_expiry = 0

        excluded_headers = {'content-encoding', 'content-length', 'transfer-encoding', 'connection'}
        response_headers = [(name, value) for (name, value) in resp.headers.items() if name.lower() not in excluded_headers]

        return Response(resp.content, status=resp.status_code, headers=response_headers)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Local Evaluation Proxy running on port 9090 (with in-memory token caching)...")
    print("Waiting for VM submissions...")
    app.run(host="127.0.0.1", port=9090, threaded=True)
