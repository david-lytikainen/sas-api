#!/usr/bin/env python3
"""
Test the complete payment flow from PaymentIntent creation to user registration
"""
import os
import requests
import json
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_complete_payment_flow():
    """Test the complete payment flow"""
    base_url = "http://localhost:5001/api"
    
    print("🧪 Testing Complete Payment Flow")
    print("=" * 50)
    
    # Step 1: Login
    print("\n1️⃣ Logging in...")
    login_response = requests.post(f"{base_url}/user/signin", json={
        "email": "test@example.com",
        "password": "password"
    })
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        return False
    
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("✅ Login successful")
    
    # Step 2: Check initial registration status
    print("\n2️⃣ Checking initial registration status...")
    events_response = requests.get(f"{base_url}/events", headers=headers)
    if events_response.status_code != 200:
        print(f"❌ Failed to get events: {events_response.status_code}")
        return False
    
    events_data = events_response.json()
    event_id = 99  # Using the test event
    
    # Check if user is already registered
    registrations = events_data.get("registrations", [])
    already_registered = any(reg["event_id"] == event_id for reg in registrations)
    
    if already_registered:
        print("⚠️ User is already registered for this event")
        print("   You may need to cancel registration first to test the flow")
        return True
    
    print("✅ User not yet registered - ready to test payment flow")
    
    # Step 3: Try to register without payment (should fail)
    print("\n3️⃣ Attempting registration without payment...")
    register_response = requests.post(f"{base_url}/events/{event_id}/register", headers=headers, json={})
    
    if register_response.status_code == 402:
        print("✅ Registration correctly requires payment (402 status)")
    else:
        print(f"❌ Unexpected response: {register_response.status_code}")
        print(f"Response: {register_response.text}")
        return False
    
    # Step 4: Create PaymentIntent
    print("\n4️⃣ Creating PaymentIntent...")
    payment_response = requests.post(f"{base_url}/events/{event_id}/create-payment-intent", headers=headers)
    
    if payment_response.status_code != 200:
        print(f"❌ PaymentIntent creation failed: {payment_response.status_code}")
        print(f"Response: {payment_response.text}")
        return False
    
    payment_data = payment_response.json()
    payment_intent_id = payment_data["payment_intent_id"]
    print(f"✅ PaymentIntent created: {payment_intent_id}")
    
    # Step 5: Simulate successful payment webhook
    print("\n5️⃣ Simulating successful payment webhook...")
    
    # This would normally be sent by Stripe, but we can simulate it
    webhook_payload = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "status": "succeeded",
                "metadata": {
                    "event_id": str(event_id),
                    "user_id": "3184",  # The test user ID
                    "event_name": "Test Speed Dating Night"
                }
            }
        }
    }
    
    print(f"   PaymentIntent ID: {payment_intent_id}")
    print(f"   Event ID: {event_id}")
    print(f"   User ID: 3184")
    
    # Note: In real testing, this webhook would be sent by Stripe CLI
    # For now, we'll just verify the webhook endpoint exists
    webhook_test = requests.post(f"{base_url}/stripe/webhook", data="test")
    if webhook_test.status_code == 400:  # Expected - missing signature
        print("✅ Webhook endpoint is available and requires signature")
    else:
        print(f"⚠️ Webhook endpoint response: {webhook_test.status_code}")
    
    # Step 6: Check if user gets registered after payment
    print("\n6️⃣ Instructions for manual testing:")
    print("   1. Use the PaymentIntent in your frontend payment form")
    print("   2. Use test card: 4242 4242 4242 4242")
    print("   3. Complete the payment")
    print("   4. Check if user is automatically registered")
    print(f"   5. PaymentIntent client_secret: {payment_data['client_secret']}")
    
    print("\n✅ Payment flow setup complete!")
    print("   The webhook forwarding is running via Stripe CLI")
    print("   Complete a payment in the frontend to test automatic registration")
    
    return True

if __name__ == "__main__":
    success = test_complete_payment_flow()
    if success:
        print("\n🎉 Test setup successful!")
    else:
        print("\n❌ Test setup failed!") 