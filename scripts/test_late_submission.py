import requests
import os
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv("../.env")

API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:5001/api")
DATABASE_URL = os.getenv("DATABASE_URL")

TEST_USER_EMAIL = "male2@test.com"
TEST_USER_PASSWORD = "test123"
TEST_UNREGISTERED_EMAIL = "admin@example.com"
TEST_UNREGISTERED_PASSWORD = "admin123"
TEST_EVENT_ID = 12
TEST_SPEED_DATE_ID = 1


def get_auth_token(email, password):
    """Logs in a user and returns the access token."""
    login_url = f"{API_BASE_URL}/user/signin"
    try:
        response = requests.post(login_url, json={"email": email, "password": password})
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
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


def get_user_id_from_email(email, db_url):
    """Get user ID from email using database connection."""
    if not db_url:
        print("Error: DATABASE_URL not found in .env file.")
        return None
    try:
        engine = create_engine(db_url)
        with engine.connect() as connection:
            query = text("SELECT id FROM users WHERE email = :email")
            result = connection.execute(query, {"email": email})
            user = result.fetchone()
            if user:
                return user[0]
            else:
                print(f"User with email {email} not found in database")
                return None
    except Exception as e:
        print(f"Error querying user from database: {e}")
        return None


def set_event_completed_long_ago(event_id, db_url):
    """Connects to the DB and sets the event status and updated_at."""
    if not db_url:
        print("Error: DATABASE_URL not found in .env file.")
        return False
    try:
        engine = create_engine(db_url)
        twenty_five_hours_ago = datetime.now(timezone.utc) - timedelta(hours=25)

        sql = text(
            """
            UPDATE events
            SET status = :status, updated_at = :updated_at
            WHERE id = :event_id
        """
        )

        with engine.connect() as connection:
            connection.execute(
                sql,
                {
                    "status": "Completed",
                    "updated_at": twenty_five_hours_ago,
                    "event_id": event_id,
                },
            )
            connection.commit()
        print(
            f"Event {event_id} status set to 'Completed' and updated_at set to {twenty_five_hours_ago}"
        )
        return True
    except Exception as e:
        print(f"Error updating event timestamp in database: {e}")
        return False


def set_event_starting_soon(event_id, db_url):
    """Connects to the DB and sets the event start time to be 1 hour from now.
    Returns the actual event ID that was created or updated."""
    if not db_url:
        print("Error: DATABASE_URL not found in .env file.")
        return False
    try:
        engine = create_engine(db_url)
        
        # Get the creator_id from the admin user
        creator_id = get_user_id_from_email(TEST_UNREGISTERED_EMAIL, db_url)
        if not creator_id:
            print(f"Could not find user ID for {TEST_UNREGISTERED_EMAIL}")
            # Fallback to finding any admin user
            with engine.connect() as connection:
                query = text("SELECT id FROM users WHERE role_id = 3 LIMIT 1")  # Admin role_id = 3
                result = connection.execute(query)
                admin = result.fetchone()
                if admin:
                    creator_id = admin[0]
                    print(f"Using admin user with ID {creator_id} as creator")
                else:
                    print("Could not find any admin user, test will fail")
                    return False
        
        # Always use UTC timezone for consistency with the application
        one_hour_from_now = datetime.now(timezone.utc) + timedelta(hours=1)
        
        print(f"Debug - Setting event to start at: {one_hour_from_now.isoformat()}")

        # First check if the event exists
        with engine.connect() as connection:
            # Enable PostgreSQL datetime debugging
            connection.execute(text("SET TIME ZONE 'UTC';"))
            
            check_sql = text("SELECT id, starts_at FROM events WHERE id = :event_id")
            result = connection.execute(check_sql, {"event_id": event_id})
            row = result.fetchone()
            event_exists = row is not None
            
            if event_exists:
                current_starts_at = row[1]
                print(f"Debug - Current event start time: {current_starts_at}")
        
        actual_event_id = event_id
        if not event_exists:
            print(f"Event {event_id} not found. Creating it...")
            # Create the event with status 'Registration Open'
            with engine.connect() as connection:
                # Ensure the connection is in UTC
                connection.execute(text("SET TIME ZONE 'UTC';"))
                
                create_sql = text("""
                INSERT INTO events 
                (name, description, creator_id, starts_at, address, max_capacity, 
                price_per_person, status, created_at, updated_at, registration_deadline)
                VALUES 
                (:name, :description, :creator_id, :starts_at, :address, :max_capacity, 
                :price_per_person, :status, :created_at, :updated_at, :registration_deadline)
                RETURNING id, starts_at
                """)
                
                now = datetime.now(timezone.utc)
                result = connection.execute(
                    create_sql,
                    {
                        "name": f"Test Event {event_id}",
                        "description": "Test event for registration cutoff testing",
                        "creator_id": creator_id,  # Use the valid creator_id
                        "starts_at": one_hour_from_now,
                        "address": "123 Test Street",
                        "max_capacity": 20,
                        "price_per_person": 0,
                        "status": "Registration Open",
                        "created_at": now,
                        "updated_at": now,
                        "registration_deadline": one_hour_from_now
                    }
                )
                connection.commit()
                new_row = result.fetchone()
                actual_event_id = new_row[0]
                new_starts_at = new_row[1]
                print(f"Created new event with ID: {actual_event_id}, starts_at: {new_starts_at}")
                
                # Verify the timezone was preserved
                verify_sql = text("SELECT starts_at AT TIME ZONE 'UTC' FROM events WHERE id = :event_id")
                result = connection.execute(verify_sql, {"event_id": actual_event_id})
                verified_time = result.fetchone()[0]
                print(f"Verified starts_at in UTC: {verified_time}")
                return actual_event_id
        else:
            # Update the existing event
            sql = text(
                """
                UPDATE events
                SET starts_at = :starts_at, status = :status, updated_at = :updated_at,
                    registration_deadline = :registration_deadline
                WHERE id = :event_id
                RETURNING starts_at
            """
            )

            with engine.connect() as connection:
                # Ensure the connection is in UTC
                connection.execute(text("SET TIME ZONE 'UTC';"))
                
                result = connection.execute(
                    sql,
                    {
                        "starts_at": one_hour_from_now,
                        "status": "Registration Open",
                        "updated_at": datetime.now(timezone.utc),
                        "registration_deadline": one_hour_from_now,
                        "event_id": event_id,
                    },
                )
                connection.commit()
                updated_starts_at = result.fetchone()[0]
            print(
                f"Event {event_id} starts_at set to {updated_starts_at} (1 hour from now)"
            )
            
            # Double-check that the update worked by querying the database again
            with engine.connect() as connection:
                verify_sql = text("SELECT starts_at FROM events WHERE id = :event_id")
                result = connection.execute(verify_sql, {"event_id": event_id})
                verified_time = result.fetchone()[0]
                print(f"Verified starts_at after update: {verified_time}")
                
                # Calculate the time difference for debugging
                now = datetime.now(timezone.utc)
                time_diff = (verified_time - now).total_seconds() / 3600
                print(f"Time until event starts: {time_diff} hours")
                
                # This should be approximately 1 hour
                if 0.9 <= time_diff <= 1.1:
                    print("✅ Time difference is correctly set to approximately 1 hour")
                else:
                    print("⚠️ WARNING: Time difference is not approximately 1 hour!")
                
            return actual_event_id
    except Exception as e:
        print(f"Error updating event start time in database: {e}")
        return False


def verify_test_data(event_id, speed_date_id, db_url):
    """Verify that both the event and speed date record actually exist in the database."""
    if not db_url:
        print("Error: DATABASE_URL not found in .env file.")
        return False
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as connection:
            # Check event exists
            event_query = text("SELECT id, status FROM events WHERE id = :event_id")
            event_result = connection.execute(event_query, {"event_id": event_id})
            event = event_result.fetchone()
            
            if not event:
                print(f"Event with ID {event_id} does not exist in database. Test will fail.")
                return False
            
            print(f"Event {event_id} exists with status: {event[1]}")
            
            # Check speed date record exists
            speed_date_query = text("SELECT id, male_id, female_id FROM events_speed_dates WHERE id = :speed_date_id AND event_id = :event_id")
            speed_date_result = connection.execute(
                speed_date_query, 
                {"speed_date_id": speed_date_id, "event_id": event_id}
            )
            speed_date = speed_date_result.fetchone()
            
            if not speed_date:
                print(f"Speed date record with ID {speed_date_id} for event {event_id} does not exist. Test will fail.")
                
                # Check any speed date records for this event
                check_query = text("SELECT COUNT(*) FROM events_speed_dates WHERE event_id = :event_id")
                check_result = connection.execute(check_query, {"event_id": event_id})
                count = check_result.fetchone()[0]
                
                if count == 0:
                    print(f"There are NO speed date records for event {event_id}.")
                else:
                    print(f"There are {count} speed date records for event {event_id}.")
                    
                    # Get first available speed date record
                    if count > 0:
                        first_record_query = text("SELECT id, male_id, female_id FROM events_speed_dates WHERE event_id = :event_id LIMIT 1")
                        first_record_result = connection.execute(first_record_query, {"event_id": event_id})
                        first_record = first_record_result.fetchone()
                        
                        if first_record:
                            print(f"First available speed date record: ID={first_record[0]}, male_id={first_record[1]}, female_id={first_record[2]}")
                            print(f"Consider updating TEST_SPEED_DATE_ID to {first_record[0]} in the script.")
                
                return False
            
            print(f"Speed date record {speed_date_id} exists for event {event_id} with male_id={speed_date[1]}, female_id={speed_date[2]}")
            return True
            
    except Exception as e:
        print(f"Error verifying test data: {e}")
        return False


def create_test_event_if_needed(db_url, user_id):
    """Creates a test event and speed date record if they don't exist already.
    Returns a tuple of (event_id, speed_date_id)"""
    if not db_url:
        print("Error: DATABASE_URL not found in .env file.")
        return None, None
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as connection:
            # First check if we already have an event with speed dates
            check_query = text("""
                SELECT e.id, (
                    SELECT MIN(sd.id) 
                    FROM events_speed_dates sd 
                    WHERE sd.event_id = e.id
                ) as speed_date_id
                FROM events e
                WHERE (
                    SELECT COUNT(*) 
                    FROM events_speed_dates sd 
                    WHERE sd.event_id = e.id
                ) > 0
                LIMIT 1
            """)
            result = connection.execute(check_query)
            row = result.fetchone()
            
            if row and row[0] and row[1]:
                print(f"Found existing event {row[0]} with speed date {row[1]}")
                return row[0], row[1]
            
            # No suitable event found, create one
            print("No suitable event found with speed dates. Creating test event...")
            
            # Get an admin user if needed
            if not user_id:
                admin_query = text("SELECT id FROM users WHERE role_id = 3 LIMIT 1")  # Admin role_id = 3
                admin_result = connection.execute(admin_query)
                admin = admin_result.fetchone()
                if admin:
                    user_id = admin[0]
                else:
                    print("Could not find an admin user to create the event")
                    return None, None
            
            # Create event
            now = datetime.now(timezone.utc)
            create_event_sql = text("""
                INSERT INTO events 
                (name, description, creator_id, starts_at, address, max_capacity, 
                price_per_person, status, created_at, updated_at, registration_deadline)
                VALUES 
                (:name, :description, :creator_id, :starts_at, :address, :max_capacity, 
                :price_per_person, :status, :created_at, :updated_at, :registration_deadline)
                RETURNING id
            """)
            
            result = connection.execute(
                create_event_sql,
                {
                    "name": "Test Event for Submission Test",
                    "description": "Test event for late submission testing",
                    "creator_id": user_id,
                    "starts_at": now - timedelta(days=1),  # Yesterday
                    "address": "123 Test Street",
                    "max_capacity": 20,
                    "price_per_person": 0,
                    "status": "Completed",
                    "created_at": now - timedelta(days=2),
                    "updated_at": now - timedelta(days=1),
                    "registration_deadline": now - timedelta(days=2)
                }
            )
            event_id = result.fetchone()[0]
            print(f"Created test event with ID: {event_id}")
            
            # Get male and female user IDs
            male_query = text("SELECT id FROM users WHERE gender = 'Male' LIMIT 1")
            female_query = text("SELECT id FROM users WHERE gender = 'Female' LIMIT 1")
            
            male_result = connection.execute(male_query)
            female_result = connection.execute(female_query)
            
            male_user = male_result.fetchone()
            female_user = female_result.fetchone()
            
            if not male_user or not female_user:
                print("Could not find both male and female users for speed date record")
                connection.rollback()
                return None, None
            
            male_id = male_user[0]
            female_id = female_user[0]
            
            # Create a speed date record
            create_speed_date_sql = text("""
                INSERT INTO events_speed_dates
                (event_id, male_id, female_id, table_number, round_number)
                VALUES
                (:event_id, :male_id, :female_id, 1, 1)
                RETURNING id
            """)
            
            result = connection.execute(
                create_speed_date_sql,
                {
                    "event_id": event_id,
                    "male_id": male_id,
                    "female_id": female_id
                }
            )
            speed_date_id = result.fetchone()[0]
            print(f"Created speed date record with ID: {speed_date_id}")
            
            # Create attendee records for the test users
            create_attendee_sql = text("""
                INSERT INTO events_attendees
                (event_id, user_id, status, pin)
                VALUES
                (:event_id, :user_id, 'Checked In', '1234')
                ON CONFLICT (event_id, user_id) DO NOTHING
            """)
            
            connection.execute(create_attendee_sql, {"event_id": event_id, "user_id": male_id})
            connection.execute(create_attendee_sql, {"event_id": event_id, "user_id": female_id})
            
            connection.commit()
            return event_id, speed_date_id
            
    except Exception as e:
        print(f"Error creating test event: {e}")
        return None, None
        

def test_late_submission():
    print("--- Test: Submitting selections > 24 hours after event completion ---")

    user_id = get_user_id_from_email(TEST_USER_EMAIL, DATABASE_URL)
    
    print(f"\nFinding or creating test event...")
    event_id, speed_date_id = create_test_event_if_needed(DATABASE_URL, user_id)
    if not event_id or not speed_date_id:
        print("Test aborted: Could not find or create test event.")
        return False
        
    global TEST_EVENT_ID, TEST_SPEED_DATE_ID
    TEST_EVENT_ID = event_id
    TEST_SPEED_DATE_ID = speed_date_id
    
    print(f"\nVerifying test data...")
    if not verify_test_data(TEST_EVENT_ID, TEST_SPEED_DATE_ID, DATABASE_URL):
        print("Test aborted: Test data verification failed.")
        return False

    print(f"\nLogging in as attendee: {TEST_USER_EMAIL}...")
    auth_token = get_auth_token(TEST_USER_EMAIL, TEST_USER_PASSWORD)
    if not auth_token:
        print("Test aborted: Could not log in attendee user.")
        return False

    print(
        f"\nSetting Event ID {TEST_EVENT_ID} to 'Completed' with updated_at > 24 hours ago..."
    )
    if not set_event_completed_long_ago(TEST_EVENT_ID, DATABASE_URL):
        print("Test aborted: Could not update event timestamp in database.")
        return False

    submit_url = f"{API_BASE_URL}/events/{TEST_EVENT_ID}/speed-date-selections"
    payload = {
        "selections": [{"event_speed_date_id": TEST_SPEED_DATE_ID, "interested": True}]
    }
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    print(f"\nAttempting to POST to {submit_url} with payload: {json.dumps(payload)}")
    try:
        response = requests.post(submit_url, headers=headers, json=payload)

        print(f"\nResponse Status Code: {response.status_code}")
        try:
            response_data = response.json()
            print(f"Response JSON: {json.dumps(response_data)}")

            if response.status_code == 400:
                print("\nSUCCESS: Received expected status code 400.")
                if (
                    "error" in response_data
                    and "24 hours after event completion" in response_data["error"]
                ):
                    print(
                        "SUCCESS: Received expected error message indicating the window is closed."
                    )
                    return True
                else:
                    print(
                        f"FAILURE: Status code is 400, but the error message is unexpected: {response_data.get('error')}"
                    )
                    return False
            elif response.status_code == 500:
                print(f"FAILURE: Server error (500) occurred. Full response text:")
                print(response.text)
                if "Traceback" in response.text:
                    print("\nServer traceback detected. Error details:")
                    error_lines = [line for line in response.text.split('\n') if "Error" in line or "Exception" in line]
                    for line in error_lines:
                        print(line.strip())
                return False
            else:
                print(
                    f"FAILURE: Expected status code 400, but received {response.status_code}."
                )
                return False

        except json.JSONDecodeError:
            print("FAILURE: Could not decode JSON response.")
            print(f"Response Text: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"\nFAILURE: Request to submit selections failed: {e}")
        return False
    except Exception as e:
        print(f"\nFAILURE: An unexpected error occurred during submission: {e}")
        return False


def test_registration_too_close_to_event():
    print("\n--- Test: Registering for an event < 2 hours before start time ---")

    print(f"\nLogging in as unregistered user: {TEST_UNREGISTERED_EMAIL}...")
    auth_token = get_auth_token(TEST_UNREGISTERED_EMAIL, TEST_UNREGISTERED_PASSWORD)
    if not auth_token:
        print("Test aborted: Could not log in unregistered user.")
        return False

    print(f"\nSetting Event ID {TEST_EVENT_ID} to start in 1 hour...")
    actual_event_id = set_event_starting_soon(TEST_EVENT_ID, DATABASE_URL)
    if not actual_event_id:
        print("Test aborted: Could not update event start time in database.")
        return False
    
    print(f"Using actual event ID: {actual_event_id} for registration test")

    register_url = f"{API_BASE_URL}/events/{actual_event_id}/register"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    print(f"\nAttempting to POST to {register_url} to register for the event...")
    try:
        response = requests.post(register_url, headers=headers)

        print(f"\nResponse Status Code: {response.status_code}")
        try:
            response_data = response.json()
            print(f"Response JSON: {json.dumps(response_data)}")

            if response.status_code == 400:
                print("\nSUCCESS: Received expected status code 400.")
                if (
                    "error" in response_data
                    and ("Registration is closed" in response_data["error"] 
                         and "within 2 hours" in response_data["error"])
                ):
                    print(
                        "SUCCESS: Received expected error message indicating registration is closed."
                    )
                    return True
                else:
                    print(
                        f"FAILURE: Status code is 400, but the error message is unexpected: {response_data.get('error')}"
                    )
                    return False
            else:
                print(
                    f"FAILURE: Expected status code 400, but received {response.status_code}."
                )
                if response.status_code == 500:
                    print("WARNING: Server error occurred. Check the server logs for details.")
                    if hasattr(response, 'text'):
                        error_text = response.text[:500] + "..." if len(response.text) > 500 else response.text
                        print(f"Error response: {error_text}")
                return False

        except json.JSONDecodeError:
            print("FAILURE: Could not decode JSON response.")
            print(f"Response Text: {response.text[:500]}...")
            return False

    except requests.exceptions.RequestException as e:
        print(f"\nFAILURE: Request to register for event failed: {e}")
        return False
    except Exception as e:
        print(f"\nFAILURE: An unexpected error occurred during registration: {e}")
        return False


if __name__ == "__main__":
    #late_submission_result = test_late_submission()
    late_registration_result = test_registration_too_close_to_event()
    
    print("\n--- Test Summary ---")
    #print(f"Late submission test: {'PASSED' if late_submission_result else 'FAILED'}")
    print(f"Late registration test: {'PASSED' if late_registration_result else 'FAILED'}")
    
    # Exit with appropriate code
    #exit(0 if late_submission_result and late_registration_result else 1)
    exit(0 if late_registration_result else 1)