import requests
import json

def check_registration_status():
    """Check if the test user is registered for the event"""
    base_url = "http://localhost:5001/api"
    
    # Login
    login_response = requests.post(f"{base_url}/user/signin", json={
        "email": "test@example.com",
        "password": "password"
    })
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        return
    
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Get events and registrations
    events_response = requests.get(f"{base_url}/events", headers=headers)
    if events_response.status_code != 200:
        print(f"❌ Failed to get events: {events_response.status_code}")
        return
    
    events_data = events_response.json()
    event_id = 99
    
    # Check registrations
    registrations = events_data.get("registrations", [])
    registration = next((reg for reg in registrations if reg["event_id"] == event_id), None)
    
    print(f"🔍 Registration Status for Event {event_id}:")
    print("=" * 40)
    
    if registration:
        print("✅ User IS registered!")
        print(f"   Status: {registration['status']}")
        print(f"   PIN: {registration.get('pin', 'N/A')}")
        print(f"   Registration Date: {registration.get('registration_date', 'N/A')}")
    else:
        print("❌ User is NOT registered")
        print("   Try completing a payment in the frontend first")
    
    print(f"\nTotal registrations for user: {len(registrations)}")

if __name__ == "__main__":
    check_registration_status() 