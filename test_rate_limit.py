import requests
import time
import os

# --- Configuration ---
# Make sure your Flask app is running!
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5001")
# !!! IMPORTANT: Change this to a real, simple GET endpoint in your API !!!
# If this endpoint requires authentication, the test might fail for other reasons.
ENDPOINT_TO_TEST = "/api/events"
# !!! IMPORTANT: Replace with a valid JWT token from your application !!!
TEST_JWT_TOKEN = "YOUR_VALID_JWT_TOKEN_HERE"
# Number of requests to send (should be > default limit of 5)
NUM_REQUESTS = 7
# Delay between requests (in seconds) - keep total time under 60s
DELAY_SECONDS = 0.5
# --- End Configuration ---

TARGET_URL = f"{BASE_URL}{ENDPOINT_TO_TEST}"

print(f"Testing rate limiting on: {TARGET_URL}")
# Add a check for the placeholder token
if TEST_JWT_TOKEN == "YOUR_VALID_JWT_TOKEN_HERE":
    print("\nWARNING: Please replace 'YOUR_VALID_JWT_TOKEN_HERE' in the script with a valid JWT token.")
    # Optionally exit if you don't want to run without a real token
    # import sys
    # sys.exit(1)

headers = {}
if TEST_JWT_TOKEN and TEST_JWT_TOKEN != "YOUR_VALID_JWT_TOKEN_HERE":
    headers['Authorization'] = f'Bearer {TEST_JWT_TOKEN}'
    print("Sending requests with Authorization header.")
else:
    print("Sending requests WITHOUT Authorization header.")

print(f"Sending {NUM_REQUESTS} requests with a {DELAY_SECONDS}s delay...")
print("-" * 30)

success_count = 0
rate_limit_hit_count = 0

for i in range(NUM_REQUESTS):
    request_num = i + 1
    print(f"Sending request {request_num}/{NUM_REQUESTS}... ", end="")
    try:
        # Add the headers to the request
        response = requests.get(TARGET_URL, headers=headers)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            success_count += 1
        elif response.status_code == 429:
            rate_limit_hit_count += 1
            print("  -> Rate limit triggered!")
        else:
            # Handle other potential statuses like 404 Not Found, 401 Unauthorized, 500 Server Error etc.
            print(f"  -> WARNING: Received unexpected status code {response.status_code}")
            # You might want to stop the test if the endpoint isn't working as expected
            # break 

    except requests.exceptions.ConnectionError as e:
        print(f"\nError: Could not connect to {BASE_URL}. Is the Flask server running?")
        print(f"Details: {e}")
        break
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        break

    # Don't sleep after the last request
    if request_num < NUM_REQUESTS:
        time.sleep(DELAY_SECONDS)

print("-" * 30)
print("Test Summary:")
print(f"  Successful requests (Status 200): {success_count}")
print(f"  Rate limited requests (Status 429): {rate_limit_hit_count}")

# Check if the results match expectations (adjust if your limit is different)
EXPECTED_SUCCESS = 5
if success_count == EXPECTED_SUCCESS and rate_limit_hit_count == (NUM_REQUESTS - EXPECTED_SUCCESS):
    print("\nResult: PASSED! Rate limiting seems to be working as expected (5 allowed, then 429).")
elif success_count < EXPECTED_SUCCESS and rate_limit_hit_count > 0:
     print(f"\nResult: PARTIAL? Rate limit triggered after {success_count} requests. Check if this matches your intended limits.")
elif rate_limit_hit_count == 0 and success_count == NUM_REQUESTS:
     print("\nResult: FAILED? No rate limit triggered. Check Flask-Limiter setup and ensure limits apply to this endpoint.")
else:
    print("\nResult: UNEXPECTED. Review the status codes received.") 