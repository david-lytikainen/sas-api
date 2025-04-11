import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) #relative imports

from decimal import Decimal
from app import create_app, db
from app.models.user import User
from app.models.enums import EventStatus, Gender, RegistrationStatus
from app.models.event import Event
from app.models.event_attendee import EventAttendee
from app.models.event_speed_date import EventSpeedDate
from datetime import datetime, timedelta
from random import randint, randrange

app = create_app()

def create_test_users():
    """Create 12 male and 17 female test users"""
    test_users = []
    
    # Create 12 male users
    for i in range(12):
        male_user = User(
            role_id=1,  # Assuming 1 is regular user role
            email=f"male{i+1}@test.com",
            password="test123",  # You might want to hash this
            first_name=f"Male{i+1}",
            last_name=f"Test{i+1}",
            phone=f"+1555000{str(i+1).zfill(4)}",
            gender=Gender.MALE,
            birthday=random_birthday(20,30),
            church_id=None,  # Optional
            denomination_id=None  # Optional
        )
        test_users.append(male_user)
    
    # Create 17 female users
    for i in range(17):
        female_user = User(
            role_id=1,  # Assuming 1 is regular user role
            email=f"female{i+1}@test.com",
            password="test123",  # You might want to hash this
            first_name=f"Female{i+1}",
            last_name=f"Test{i+1}",
            phone=f"+1555111{str(i+1).zfill(4)}",
            gender=Gender.FEMALE,
            birthday=random_birthday(20,30),
            church_id=None,  # Optional
            denomination_id=None  # Optional
        )
        test_users.append(female_user)
    
    # Add all users to database
    db.session.add_all(test_users)
    db.session.commit()
    
    print(f"Created {len(test_users)} test users ({12} males, {17} females)")
    return test_users

def random_birthday(min_age, max_age):
    today = datetime.now()
    start_date = today.replace(year=today.year - max_age)
    end_date = today.replace(year=today.year - min_age)
    random_date = start_date + timedelta(days=randrange((end_date - start_date).days))
    return random_date.date()

def create_test_event(creator_id):
    """Create a test event for speed dating"""
    
    # Set event times (example: event tomorrow from 7pm-10pm)
    tomorrow = datetime.now() + timedelta(days=1)
    starts_at = tomorrow.replace(hour=19, minute=0, second=0, microsecond=0)
    ends_at = tomorrow.replace(hour=22, minute=0, second=0, microsecond=0)
    
    test_event = Event(
        creator_id=creator_id,
        starts_at=starts_at,
        ends_at=ends_at,
        address="123 Test Street, Test City, TS 12345",
        name="Test Speed Dating Night",
        max_capacity=50,  # More than our test users
        status=EventStatus.PUBLISHED,
        price_per_person=Decimal("25.00"),
        registration_deadline=starts_at - timedelta(hours=2),
        description="Test speed dating event for singles aged 22-30"
    )
    
    db.session.add(test_event)
    db.session.commit()
    
    print(f"Created test event: {test_event.name}")
    return test_event

def create_test_attendees(test_users, test_event):
    """Create event attendees from our test users"""
    test_attendees = []
    
    # Register all test users for the event
    for user in test_users:
        attendee = EventAttendee(
            event_id=test_event.id,
            user_id=user.id,
            status=RegistrationStatus.CHECKED_IN,  # Making them all checked in for testing
            check_in_date=datetime.now()  # Since we're testing speed dating matching
        )
        test_attendees.append(attendee)
    
    db.session.add_all(test_attendees)
    db.session.commit()
    
    print(f"Created {len(test_attendees)} test attendees for event")
    return test_attendees

def delete_test_data():
    """Delete all test data from the database"""
    db.session.query(EventAttendee).delete()
    db.session.query(Event).delete()
    db.session.query(User).delete()
    db.session.commit()

def main():
    with app.app_context():
        delete_test_data()
        test_users = create_test_users()
        test_event = create_test_event(test_users[0].id)
        create_test_attendees(test_users, test_event)
        
if __name__ == "__main__":
    main() 