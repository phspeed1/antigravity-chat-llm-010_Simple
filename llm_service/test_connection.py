
import requests
import os
import sys

def test_connection():
    url = "http://localhost:8000"
    print(f"Testing connection to {url}...")
    
    try:
        # 1. Health Check
        print("1. Sending health check request...")
        resp = requests.get(f"{url}/")
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.text}")
        
        # 2. Session Check (with dummy token to trigger 401 log)
        print("\n2. Sending authenticated request (expecting 401 or 500)...")
        headers = {"Authorization": "Bearer dummy_token"}
        resp = requests.get(f"{url}/sessions", headers=headers)
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.text}")
        
    except Exception as e:
        print(f"\n[FATAL] Connection failed: {e}")
        print("Make sure the server is running on port 8000.")

if __name__ == "__main__":
    test_connection()
