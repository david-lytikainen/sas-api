#!/usr/bin/env python3
"""
Simulate Stripe webhook events for development testing
This allows testing payment flow without running Stripe CLI
"""
import requests
import json
import time
import hashlib
import hmac
from datetime import datetime

class WebhookSimulator:
    def __init__(self, base_url="http://localhost:5001/api"):
        self.base_url = base_url
        self.webhook_secret = "whsec_test_development_secret"  # Use a test secret for dev
        
    def create_webhook_signature(self, payload, timestamp):
        """Create a valid Stripe webhook signature"""
        signed_payload = f"{timestamp}.{payload}"
        signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={signature}"
    
    def simulate_payment_success(self, event_id, user_id, payment_intent_id=None):
        """Simulate a successful payment webhook"""
        if not payment_intent_id:
            payment_intent_id = f"pi_test_{int(time.time())}"
            
        # Create webhook payload
        timestamp = int(time.time())
        webhook_payload = {
            "id": f"evt_test_{int(time.time())}",
            "object": "event",
            "api_version": "2020-08-27",
            "created": timestamp,
            "data": {
                "object": {
                    "id": payment_intent_id,
                    "object": "payment_intent",
                    "amount": 2000,  # $20.00 in cents
                    "currency": "usd",
                    "status": "succeeded",
                    "metadata": {
                        "event_id": str(event_id),
                        "user_id": str(user_id),
                        "event_name": "Test Event"
                    }
                }
            },
            "livemode": False,
            "pending_webhooks": 1,
            "request": {
                "id": f"req_test_{int(time.time())}",
                "idempotency_key": None
            },
            "type": "payment_intent.succeeded"
        }
        
        payload_str = json.dumps(webhook_payload, separators=(',', ':'))
        signature = self.create_webhook_signature(payload_str, timestamp)
        
        print(f"🎯 Simulating payment_intent.succeeded webhook...")
        print(f"   Event ID: {event_id}")
        print(f"   User ID: {user_id}")
        print(f"   Payment Intent: {payment_intent_id}")
        
        try:
            response = requests.post(
                f"{self.base_url}/stripe/webhook",
                data=payload_str,
                headers={
                    "Content-Type": "application/json",
                    "Stripe-Signature": signature
                }
            )
            
            if response.status_code == 200:
                print(f"✅ Webhook processed successfully!")
                print(f"   Response: {response.json()}")
                return True
            else:
                print(f"❌ Webhook failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending webhook: {e}")
            return False

def main():
    """Test webhook simulation"""
    print("🧪 Stripe Webhook Simulator")
    print("=" * 40)
    
    simulator = WebhookSimulator()
    
    # You can customize these values
    event_id = 99  # Change to your test event ID
    user_id = 3184  # Change to your test user ID
    
    print(f"\n📋 Test Configuration:")
    print(f"   Backend URL: {simulator.base_url}")
    print(f"   Event ID: {event_id}")
    print(f"   User ID: {user_id}")
    
    # Simulate successful payment
    success = simulator.simulate_payment_success(event_id, user_id)
    
    if success:
        print(f"\n🎉 Payment simulation completed!")
        print(f"   User {user_id} should now be registered for event {event_id}")
        print(f"   Check the registration status with: python check_registration_status.py")
    else:
        print(f"\n❌ Payment simulation failed")
        print(f"   Make sure your Flask server is running on port 5001")

if __name__ == "__main__":
    main() 