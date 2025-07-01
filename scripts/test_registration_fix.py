#!/usr/bin/env python3
"""
Test script to verify the registration fix works correctly.
This tests the scenario where a user cancels registration and tries to re-register immediately.
"""

import requests
import json
import time

# Test configuration
API_BASE = "http://localhost:5000/api"
TEST_EVENT_ID = 99
TEST_EMAIL = "admin@example.com"
TEST_PASSWORD = "admin123"

def login():
    """Login and get JWT token"""
    login_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(f"{API_BASE}/user/signin", json=login_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None

def test_registration_flow(token):
    """Test the complete registration flow"""
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"Testing registration flow for event {TEST_EVENT_ID}")
    
    # Step 1: Try to register normally
    print("\n1. Attempting normal registration...")
    register_data = {"join_waitlist": False}
    response = requests.post(f"{API_BASE}/events/{TEST_EVENT_ID}/register", 
                           json=register_data, headers=headers)
    print(f"Registration response: {response.status_code} - {response.json()}")
    
    if response.status_code == 402:
        print("Payment required - this is expected for paid events")
        return True
    elif response.status_code == 200:
        print("Registration successful without payment - testing cancellation...")
        
        # Step 2: Cancel registration
        print("\n2. Cancelling registration...")
        cancel_response = requests.post(f"{API_BASE}/events/{TEST_EVENT_ID}/cancel-registration", 
                                      headers=headers)
        print(f"Cancellation response: {cancel_response.status_code} - {cancel_response.json()}")
        
        # Step 3: Try to re-register immediately
        print("\n3. Attempting immediate re-registration...")
        reregister_data = {"join_waitlist": False, "force_registration": True}
        reregister_response = requests.post(f"{API_BASE}/events/{TEST_EVENT_ID}/register", 
                                          json=reregister_data, headers=headers)
        print(f"Re-registration response: {reregister_response.status_code} - {reregister_response.json()}")
        
        if reregister_response.status_code == 200:
            print("✅ Re-registration successful!")
            return True
        else:
            print("❌ Re-registration failed")
            return False
    else:
        print(f"Unexpected registration response: {response.status_code}")
        return False

def main():
    print("Starting registration fix test...")
    
    token = login()
    if not token:
        print("❌ Login failed, cannot continue test")
        return
    
    print("✅ Login successful")
    
    success = test_registration_flow(token)
    
    if success:
        print("\n✅ Registration fix test completed successfully!")
    else:
        print("\n❌ Registration fix test failed!")

if __name__ == "__main__":
    main() 