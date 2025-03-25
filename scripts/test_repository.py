import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.repositories.event_attendee_repository import EventAttendeeRepository

app = create_app()

def test_repository():
    with app.app_context():
        # Get the event_id from our test data
        event_id = 2  # assuming this is our test event's id
        
        # Test first method
        print("\nTesting find_by_event_id_and_checked_in:")
        attendees = EventAttendeeRepository.find_by_event_id_and_checked_in(event_id)
        print(attendees[0])
        # for ea, user in attendees:
        #     print(f"Attendee: {user.first_name} {user.last_name}, Gender: {user.gender}")
            
        # Test gender grouped method
        # print("\nTesting find_by_event_id_and_checked_in_grouped_by_gender:")
        # males, females = EventAttendeeRepository.find_by_event_id_and_checked_in_grouped_by_gender(event_id)
        # print(f"Male attendees: {len(males)}")
        # print(f"Female attendees: {len(females)}")

if __name__ == "__main__":
    test_repository()