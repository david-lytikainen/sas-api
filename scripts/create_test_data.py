import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # relative imports

from decimal import Decimal
from app import create_app, db
from app.models.user import User
from app.models.enums import EventStatus, Gender, RegistrationStatus
from app.models.event import Event
from app.models.event_attendee import EventAttendee
from app.models.event_speed_date import EventSpeedDate
from app.models.event_timer import EventTimer
from datetime import datetime, timedelta
from random import randrange
from werkzeug.security import generate_password_hash
from scripts.create_admin import create_admin_user
from app.models.church import Church
from app.services.event_service import EventService

app = create_app()

# Print the database URI the app is configured to use
with app.app_context():
    print(f"INFO: Connecting to database: {app.config['SQLALCHEMY_DATABASE_URI']}")


def create_test_churches():
    """Create test churches and return a list of their IDs"""
    church_names = [
        "Calvary Chapel Delco",
        "Church of the Saviour",
        "Providence",
        "Church of God",
    ]
    churches = []
    for name in church_names:
        church = Church(name=name)
        churches.append(church)
    db.session.add_all(churches)
    db.session.commit()
    print(f"Created {len(churches)} test churches")
    return [church.id for church in churches]


def create_test_users(church_ids=None):
    """Create 12 male and 17 female test users, assigning them to churches if provided"""
    test_users = []
    if not church_ids:
        church_ids = [None]  # Default to None if no churches provided

    # Create 12 male users
    for i in range(12):
        male_user = User(
            role_id=1,  # Assuming 1 is regular user role
            email=f"male{i+1}@test.com",
            password=generate_password_hash("test123"),
            first_name=f"Male{i+1}",
            last_name=f"Test{i+1}",
            phone=f"+1555000{str(i+1).zfill(4)}",
            gender=Gender.MALE,
            birthday=random_birthday(20, 30),
            church_id=church_ids[i % len(church_ids)] if church_ids else None,
            denomination_id=None,
        )
        test_users.append(male_user)

    # Create 17 female users
    for i in range(17):
        female_user = User(
            role_id=1,  # Assuming 1 is regular user role
            email=f"female{i+1}@test.com",
            password=generate_password_hash("test123"),
            first_name=f"Female{i+1}",
            last_name=f"Test{i+1}",
            phone=f"+1555111{str(i+1).zfill(4)}",
            gender=Gender.FEMALE,
            birthday=random_birthday(20, 30),
            church_id=church_ids[i % len(church_ids)] if church_ids else None,
            denomination_id=None,
        )
        test_users.append(female_user)

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


def create_direct_attendee(event, user):
    """Directly create an attendee record bypassing all payment and capacity checks"""
    from app.repositories.event_attendee_repository import EventAttendeeRepository
    from app.repositories.event_waitlist_repository import EventWaitlistRepository
    import random
    
    # Check current capacity to decide between registration and waitlist
    attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
        event.id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
    )
    
    # Check gender capacity
    same_gender_count = EventAttendeeRepository.count_by_event_and_status_and_gender(
        event.id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN], user.gender
    )
    
    # Determine if we should register or waitlist
    event_full = attendee_count >= event.max_capacity
    gender_full = same_gender_count >= (event.max_capacity * 0.6)
    
    if event_full or gender_full:
        # Add to waitlist
        try:
            EventWaitlistRepository.add_to_waitlist(event.id, user.id)
            return {"message": "Successfully added to waitlist"}
        except Exception as e:
            return {"error": f"Failed to add to waitlist: {str(e)}"}
    else:
        # Register directly
        pin = "".join(random.choices("0123456789", k=4))
        try:
            EventAttendeeRepository.register_for_event({
                "event_id": event.id,
                "user_id": user.id,
                "status": RegistrationStatus.REGISTERED,
                "pin": pin,
            })
            return {"message": "Successfully registered for event"}
        except Exception as e:
            return {"error": f"Failed to register: {str(e)}"}


def create_test_event(creator_id, event_type="paid"):
    """Create a test event for speed dating
    
    Args:
        creator_id: ID of the user creating the event
        event_type: "paid", "free", or "both" - determines pricing
    """

    # Set event time (example: event tomorrow at 7pm)
    tomorrow = datetime.now() + timedelta(days=1)
    starts_at = tomorrow.replace(hour=19, minute=0, second=0, microsecond=0)

    # Determine pricing based on event_type
    if event_type == "free":
        price = Decimal("0.00")
        name = "Free Test Speed Dating Night"
    else:  # "paid" or default
        price = Decimal("25.00")
        name = "Test Speed Dating Night"

    test_event = Event(
        creator_id=creator_id,
        starts_at=starts_at,
        address="123 Test Street, Test City, TS 12345",
        name=name,
        max_capacity=5,  # Reduced max_capacity to test waitlist
        status="Registration Open",  # Changed to Registration Open to allow registrations
        price_per_person=price,
        registration_deadline=starts_at - timedelta(hours=2),
        description="Test speed dating event for singles aged 22-30",
        num_tables=10,
        num_rounds=10,
    )

    db.session.add(test_event)
    db.session.commit()

    from app.services.event_timer_service import EventTimerService

    EventTimerService.create_timer(test_event.id)

    return test_event


def create_test_attendees(test_users, test_event, bypass_payment=True):
    """Create event attendees from our test users
    
    Args:
        test_users: List of User objects to register
        test_event: Event object to register users for
        bypass_payment: If True, bypass payment requirements (default: True)
    """
    print(
        f"Attempting to register {len(test_users)} users for event '{test_event.name}' (ID: {test_event.id}) with max capacity {test_event.max_capacity}..."
    )
    if bypass_payment:
        print("   💰 Payment requirements will be bypassed for test data")
    else:
        print("   💳 Payment requirements will be enforced (testing real flow)")
    
    registered_count = 0
    waitlisted_count = 0
    failed_count = 0

    for user in test_users:
        try:
            if bypass_payment and test_event.price_per_person > 0:
                # For test data with paid events, directly create attendee records to completely bypass payment
                response = create_direct_attendee(test_event, user)
            else:
                # Use normal registration flow (may require payment)
                response = EventService.register_for_event(
                    event_id=test_event.id,
                    user_id=user.id,
                    join_waitlist=True,  # Important for waitlist functionality
                    payment_completed=bypass_payment,  # Bypass payment if requested
                )

            message_text = ""
            is_error = False
            status_code_from_response = None

            if isinstance(response, tuple) and len(response) == 2:
                message_dict, status_code_from_response = response
                if status_code_from_response >= 400:
                    is_error = True
                    message_text = message_dict.get("error", str(message_dict))
                else:
                    message_text = message_dict.get("message", str(message_dict))
            elif isinstance(response, dict):
                if "error" in response:
                    is_error = True
                    message_text = response.get("error", str(response))
                elif "message" in response:
                    message_text = response.get("message", str(response))
                else:
                    message_text = str(response)  # fallback for unknown dict structure
            else:
                message_text = f"Unexpected response type: {str(response)}"
                is_error = True  # Treat unexpected types as errors for counting

            if is_error:
                print(
                    f"Failed to register/waitlist user {user.email} for event {test_event.id}. Response: {message_text}"
                )
                failed_count += 1
            else:
                if "Successfully registered" in message_text:
                    print(
                        f"User {user.email} successfully registered for event {test_event.id}."
                    )
                    registered_count += 1
                elif (
                    "Successfully added to waitlist" in message_text
                    or "Successfully joined the waitlist" in message_text
                ):
                    print(
                        f"User {user.email} added to waitlist for event {test_event.id}."
                    )
                    waitlisted_count += 1
                elif (
                    status_code_from_response == 200 or status_code_from_response == 201
                ):  # Catch-all for other success
                    print(
                        f"Registration processed for user {user.email} for event {test_event.id}: {message_text}"
                    )
                    registered_count += 1  # Assume registration if not explicitly waitlisted and success code
                else:
                    # This case should ideally not be hit if logic above is correct
                    print(
                        f"Unhandled successful response for user {user.email}: {message_text}. Counting as failed."
                    )
                    failed_count += 1

        except Exception as e:
            print(
                f"Exception during registration for user {user.email} for event {test_event.id}: {str(e)}"
            )
            failed_count += 1

    # Note: We are not directly creating EventAttendee records here anymore.
    # The EventService.register_for_event handles creating EventAttendee or EventWaitlist records.
    # To check in users, we'd need a separate loop after this,
    # fetching actual registrations and then checking them in.
    # For now, this focuses on getting them registered or waitlisted.

    print(f"\nRegistration attempt summary for event {test_event.id}:")
    print(f"  Successfully registered: {registered_count}")
    print(f"  Added to waitlist: {waitlisted_count}")
    print(f"  Failed attempts: {failed_count}")

    # If you want to then check-in the successfully registered users:
    print("\nAttempting to check-in successfully registered users...")
    checked_in_count = 0
    # Only fetch users who are actually in EventAttendee table with REGISTERED status
    actually_registered_attendees = (
        EventAttendee.query.join(User)
        .filter(
            EventAttendee.event_id == test_event.id,
            EventAttendee.status == RegistrationStatus.REGISTERED,
        )
        .all()
    )

    print(
        f"Found {len(actually_registered_attendees)} users with status REGISTERED for event {test_event.id}."
    )

    for attendee_record in actually_registered_attendees:
        try:
            # Simulate check-in using the service or directly update status
            # For simplicity here, directly updating. In a real scenario, use a service if available.
            attendee_record.status = RegistrationStatus.CHECKED_IN
            attendee_record.check_in_date = datetime.now()
            attendee_record.pin = "1234"  # Example PIN
            db.session.add(attendee_record)
            print(f"Marking user ID {attendee_record.user_id} as CHECKED_IN.")
            checked_in_count += 1
        except Exception as e:
            print(f"Failed to check in user ID {attendee_record.user_id}: {str(e)}")

    if actually_registered_attendees:  # only commit if there's something to commit
        db.session.commit()
    print(f"Successfully checked in {checked_in_count} users.")

    # No return value needed as attendees are created by the service


def delete_test_data():
    """Delete all test data from the database"""
    print("Deleting test data...")
    try:
        # Delete in proper order to respect foreign keys
        db.session.query(EventSpeedDate).delete()
        db.session.query(EventTimer).delete()
        db.session.query(EventAttendee).delete()
        # Need to also delete from EventWaitlist if it exists
        from app.models.event_waitlist import (
            EventWaitlist,
        )  # Import here if not already

        db.session.query(EventWaitlist).delete()
        db.session.query(Event).delete()
        db.session.query(User).delete()
        db.session.query(Church).delete()
        db.session.commit()
        print("All test data deleted successfully")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting test data: {e}")
        raise


def have_attendees_match(event: Event):
    """Force all EventSpeedDate records for the event to be mutual matches (male_interested and female_interested True)"""
    db.session.query(EventSpeedDate).filter(EventSpeedDate.event_id == event.id).update(
        {"male_interested": True, "female_interested": True}, synchronize_session=False
    )

    print(f"Updated all event speed dates to have matches for event {event.id}")
    print(
        db.session.query(EventSpeedDate)
        .filter(EventSpeedDate.event_id == event.id)
        .all()
    )
    db.session.commit()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Create test data for SAS API')
    parser.add_argument('--event-type', choices=['free', 'paid', 'both'], default='both',
                       help='Type of events to create (default: both)')
    parser.add_argument('--no-payment-bypass', action='store_true',
                       help='Do not bypass payment requirements (test real payment flow)')
    args = parser.parse_args()
    
    with app.app_context():
        delete_test_data()
        church_ids = create_test_churches()
        test_users = create_test_users(church_ids)
        
        events_created = []
        
        if args.event_type in ['free', 'both']:
            print("\n=== Creating FREE test event ===")
            free_event = create_test_event(test_users[0].id, "free")
            events_created.append(free_event)
            create_test_attendees(test_users, free_event, bypass_payment=(not args.no_payment_bypass))
        
        if args.event_type in ['paid', 'both']:
            print("\n=== Creating PAID test event ===")
            paid_event = create_test_event(test_users[1].id, "paid")
            events_created.append(paid_event)
            create_test_attendees(test_users, paid_event, bypass_payment=(not args.no_payment_bypass))
        
        # Optionally create matches for all events
        # for event in events_created:
        #     have_attendees_match(event)
        
        create_admin_user(update=True)
        
        print(f"\n✅ Successfully created {len(events_created)} test event(s)")
        for event in events_created:
            print(f"   - {event.name} (ID: {event.id}) - Price: ${event.price_per_person}")


if __name__ == "__main__":
    main()
