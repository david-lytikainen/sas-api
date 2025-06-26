#!/usr/bin/env python3
"""
Test different payment scenarios for the Stripe integration
This script helps test success, failure, and edge cases
"""
import os
import sys
import time
from dotenv import load_dotenv
import requests
import json

# Load environment variables
load_dotenv()

class PaymentTester:
    def __init__(self):
        self.base_url = "http://localhost:5001/api"
        self.stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')
        self.auth_token = None
        
    def login_test_user(self, email="test@example.com", password="password"):
        """Login as a test user to get auth token"""
        print("🔐 Logging in test user...")
        
        login_data = {
            "email": email,
            "password": password
        }
        
        try:
            response = requests.post(f"{self.base_url}/user/signin", json=login_data)
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get('access_token')
                print(f"✅ Login successful")
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def get_headers(self):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_stripe_config(self):
        """Test getting Stripe configuration"""
        print("\n🔧 Testing Stripe config endpoint...")
        
        try:
            response = requests.get(f"{self.base_url}/stripe/config", headers=self.get_headers())
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Stripe config retrieved: {data.get('publishable_key', '')[:20]}...")
                return True
            else:
                print(f"❌ Failed to get Stripe config: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Stripe config error: {e}")
            return False
    
    def test_create_payment_intent(self, event_id=99):
        """Test creating a PaymentIntent"""
        print(f"\n💳 Testing PaymentIntent creation for event {event_id}...")
        
        try:
            response = requests.post(
                f"{self.base_url}/events/{event_id}/create-payment-intent",
                headers=self.get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                client_secret = data.get('client_secret')
                payment_intent_id = data.get('payment_intent_id')
                print(f"✅ PaymentIntent created successfully")
                print(f"   Payment Intent ID: {payment_intent_id}")
                print(f"   Client Secret: {client_secret[:20]}...")
                return data
            else:
                print(f"❌ PaymentIntent creation failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return None
        except Exception as e:
            print(f"❌ PaymentIntent error: {e}")
            return None
    
    def test_webhook_endpoint(self):
        """Test webhook endpoint (without signature - just to see if it exists)"""
        print("\n🔗 Testing webhook endpoint availability...")
        
        try:
            # Send a simple POST to see if endpoint exists
            response = requests.post(f"{self.base_url}/stripe/webhook", 
                                   data="test", 
                                   headers={"Content-Type": "application/json"})
            
            # We expect this to fail with 400 (missing signature) rather than 404
            if response.status_code == 400:
                print("✅ Webhook endpoint exists and requires signature (as expected)")
                return True
            elif response.status_code == 404:
                print("❌ Webhook endpoint not found")
                return False
            else:
                print(f"✅ Webhook endpoint responding (status: {response.status_code})")
                return True
        except Exception as e:
            print(f"❌ Webhook test error: {e}")
            return False
    
    def simulate_successful_webhook(self, event_id=1, user_id=1):
        """Simulate a successful payment webhook (for testing purposes)"""
        print(f"\n🎯 Simulating successful payment webhook...")
        print("   (This would normally be sent by Stripe)")
        
        # Mock webhook payload structure
        webhook_payload = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_123456789",
                    "amount": 2000,  # $20.00
                    "currency": "usd",
                    "status": "succeeded",
                    "metadata": {
                        "event_id": str(event_id),
                        "user_id": str(user_id),
                        "event_name": "Test Event"
                    }
                }
            }
        }
        
        print(f"   Event ID: {event_id}")
        print(f"   User ID: {user_id}")
        print(f"   Amount: $20.00")
        print("   Status: succeeded")
        
        return webhook_payload
    
    def get_events(self):
        """Get list of events to test with"""
        print("\n📅 Getting events list...")
        
        try:
            response = requests.get(f"{self.base_url}/events", headers=self.get_headers())
            if response.status_code == 200:
                events = response.json()
                paid_events = [e for e in events if float(e.get('price_per_person', 0)) > 0]
                print(f"✅ Found {len(events)} total events, {len(paid_events)} paid events")
                return events, paid_events
            else:
                print(f"❌ Failed to get events: {response.status_code}")
                return [], []
        except Exception as e:
            print(f"❌ Events error: {e}")
            return [], []

def main():
    """Run payment integration tests"""
    print("🧪 Payment Integration Test Suite")
    print("=" * 50)
    
    tester = PaymentTester()
    
    # Test sequence
    tests = [
        ("User Login", lambda: tester.login_test_user()),
        ("Stripe Config", lambda: tester.test_stripe_config()),
        ("Events List", lambda: tester.get_events()),
        ("Webhook Endpoint", lambda: tester.test_webhook_endpoint()),
        ("PaymentIntent Creation", lambda: tester.test_create_payment_intent()),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            if result:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print(f"\n{'='*50}")
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All payment tests passed!")
        print("\n📋 Manual Testing Instructions:")
        print("1. Start your Flask server: python run.py")
        print("2. Start webhook forwarding: stripe listen --forward-to localhost:5001/api/stripe/webhook")
        print("3. Start your React frontend: npm start")
        print("4. Create a paid event (price > $0)")
        print("5. Try to register with test cards:")
        print("   - Success: 4242 4242 4242 4242")
        print("   - Decline: 4000 0000 0000 0002")
        print("   - 3D Secure: 4000 0000 0000 3220")
        
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed.")
        print("Please ensure your Flask server is running and configured correctly.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 