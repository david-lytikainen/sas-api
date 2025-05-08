import requests
import os
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('../.env')

API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:5001/api")
DATABASE_URL = os.getenv("DATABASE_URL")

TEST_USER_EMAIL = "male2@test.com" 
TEST_USER_PASSWORD = "test123"          
TEST_EVENT_ID = 12
TEST_SPEED_DATE_ID = 1


def get_auth_token(email, password):
    """Logs in a user and returns the access token."""
    login_url = f"{API_BASE_URL}/user/signin"
    try:
        response = requests.post(login_url, json={"email": email, "password": password})
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        if "token" in data:
            print(f"Successfully logged in as {email}")
            return data["token"]
        else:
            print(f"Login failed for {email}: 'token' not in response")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Login request failed: {e}")
        if e.response is not None:
            print(f"Response status: {e.response.status_code}")
            try:
                print(f"Response body: {e.response.json()}")
            except json.JSONDecodeError:
                print(f"Response body: {e.response.text}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during login: {e}")
        return None

def set_event_completed_long_ago(event_id, db_url):
    """Connects to the DB and sets the event status and updated_at."""
    if not db_url:
        print("Error: DATABASE_URL not found in .env file.")
        return False
    try:
        engine = create_engine(db_url)
        twenty_five_hours_ago = datetime.now(timezone.utc) - timedelta(hours=25)
        
        sql = text("""
            UPDATE events
            SET status = :status, updated_at = :updated_at
            WHERE id = :event_id
        """)
        
        with engine.connect() as connection:
            connection.execute(sql, {
                "status": "Completed", 
                "updated_at": twenty_five_hours_ago, 
                "event_id": event_id
            })
            connection.commit()
        print(f"Event {event_id} status set to 'Completed' and updated_at set to {twenty_five_hours_ago}")
        return True
    except Exception as e:
        print(f"Error updating event timestamp in database: {e}")
        return False


if __name__ == "__main__":
    print("--- Test: Submitting selections > 24 hours after event completion ---")

    # 1. Log in as the attendee
    print(f"\nLogging in as attendee: {TEST_USER_EMAIL}...")
    auth_token = get_auth_token(TEST_USER_EMAIL, TEST_USER_PASSWORD)
    if not auth_token:
        print("Test aborted: Could not log in attendee user.")
        exit(1)

    # 2. Manually set the event's status to 'Completed' and timestamp to > 24 hours ago
    print(f"\nSetting Event ID {TEST_EVENT_ID} to 'Completed' with updated_at > 24 hours ago...")
    if not set_event_completed_long_ago(TEST_EVENT_ID, DATABASE_URL):
         print("Test aborted: Could not update event timestamp in database.")
         exit(1)

    submit_url = f"{API_BASE_URL}/events/{TEST_EVENT_ID}/speed-date-selections"
    payload = {
        "selections": [
            {"event_speed_date_id": TEST_SPEED_DATE_ID, "interested": True}
        ]
    }
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    # 4. Attempt to submit selections
    print(f"\nAttempting to POST to {submit_url} with payload: {json.dumps(payload)}")
    try:
        response = requests.post(submit_url, headers=headers, json=payload)

        # 5. Verify the response
        print(f"\nResponse Status Code: {response.status_code}")
        try:
            response_data = response.json()
            print(f"Response JSON: {json.dumps(response_data)}")

            if response.status_code == 400:
                print("\nSUCCESS: Received expected status code 400.")
                if "error" in response_data and "24 hours after event completion" in response_data["error"]:
                    print("SUCCESS: Received expected error message indicating the window is closed.")
                else:
                    print(f"FAILURE: Status code is 400, but the error message is unexpected: {response_data.get('error')}")
            else:
                print(f"FAILURE: Expected status code 400, but received {response.status_code}.")

        except json.JSONDecodeError:
            print("FAILURE: Could not decode JSON response.")
            print(f"Response Text: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"\nFAILURE: Request to submit selections failed: {e}")
    except Exception as e:
        print(f"\nFAILURE: An unexpected error occurred during submission: {e}")

    print("\n--- Test Finished ---")
