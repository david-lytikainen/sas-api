#!/usr/bin/env python3
"""
Direct registration test - bypasses webhooks for development testing
This directly calls the EventService to register a user as if payment succeeded
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.event_service import EventService

def test_direct_registration():
    """Test direct registration without webhooks"""
    print("🧪 Direct Registration Test")
    print("=" * 40)
    
    # Create app context
    app = create_app()
    with app.app_context():
        event_id = 99  # Change to your test event ID
        user_id = 3184  # Change to your test user ID
        
        print(f"📋 Test Configuration:")
        print(f"   Event ID: {event_id}")
        print(f"   User ID: {user_id}")
        
        print(f"\n🎯 Attempting direct registration...")
        
        try:
            # Call the registration service directly with payment_completed=True
            result = EventService.register_for_event(
                event_id, user_id, join_waitlist=False, payment_completed=True
            )
            
            if "error" in result:
                print(f"❌ Registration failed: {result['error']}")
                return False
            else:
                print(f"✅ Registration successful!")
                print(f"   Result: {result}")
                return True
                
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False

def main():
    """Run the direct registration test"""
    success = test_direct_registration()
    
    if success:
        print(f"\n🎉 Direct registration completed!")
        print(f"   This simulates what happens when a webhook processes a payment")
        print(f"   Check registration status with: python check_registration_status.py")
    else:
        print(f"\n❌ Direct registration failed")
        print(f"   Check that the event and user exist in the database")

if __name__ == "__main__":
    main() 