from datetime import datetime, timezone
from decimal import Decimal
import math
import random
from app.repositories.event_repository import EventRepository
from app.repositories.user_repository import UserRepository
from app.repositories.event_attendee_repository import EventAttendeeRepository
from app.repositories.event_waitlist_repository import EventWaitlistRepository
from app.exceptions import UnauthorizedError, MissingFieldsError
from app.models.enums import EventStatus, Gender, RegistrationStatus
from app.models import Event
from typing import List


class EventService:
    @staticmethod
    def get_events() -> List[Event]:
        return EventRepository.get_events()

    @staticmethod
    def get_events_for_user(user_id):
        user = UserRepository.find_by_id(user_id)
        if not user:
            return ({"error": "User not found"}), 404

        events = EventRepository.get_events()
        return [event.to_dict() for event in events]

    @staticmethod
    def create_event(data, user_id):
        user = UserRepository.find_by_id(user_id)

        if user.role_id not in [2, 3]:  # 2 = Organizer, 3 = Admin
            raise UnauthorizedError()

        required_fields = [
            "name",
            "starts_at",
            "address",
            "max_capacity",
            "price_per_person",
        ]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise MissingFieldsError(missing)

        event = EventRepository.create_event(
            {
                "name": data["name"],
                "description": data["description"],
                "creator_id": user_id,
                "starts_at": datetime.fromisoformat(
                    data["starts_at"].replace("Z", "+00:00")
                ).astimezone(timezone.utc),
                "address": data["address"],
                "max_capacity": data["max_capacity"],
                "status": EventStatus.REGISTRATION_OPEN.value,
                "price_per_person": Decimal(str(data["price_per_person"])),
                "registration_deadline": datetime.fromisoformat(
                    data["starts_at"].replace("Z", "+00:00")
                ).astimezone(timezone.utc),
            }
        )

        return event

    @staticmethod
    def register_for_event(event_id: int, user_id: int, join_waitlist: bool = False):
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}

        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return {"error": "Event is not open for registration"}

        # Check if user is already registered for this event
        existing_registration = EventAttendeeRepository.find_by_event_and_user(
            event_id, user_id
        )
        if existing_registration:
            return {"error": "You are already registered for this event"}

        # Check if user is already on the waitlist
        on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
        if on_waitlist:
            return {"error": "You are already on the waitlist for this event"}

        # Check if the event is full
        attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
        )
        if attendee_count >= event.max_capacity:
            if join_waitlist:
                return EventService.join_event_waitlist(event_id, user_id)
            else:
                return {
                    "error": "Event is full, cannot register",
                    "waitlist_available": True,
                }

        # check if event is full for this gender
        user = UserRepository.find_by_id(user_id)
        if not user:
            return {"error": f"User with ID {user_id} not found"}
        same_gender_count = (
            EventAttendeeRepository.count_by_event_and_status_and_gender(
                event_id,
                [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN],
                user.gender,
            )
        )
        if same_gender_count >= math.floor(event.max_capacity * 0.6):
            if join_waitlist:
                return EventService.join_event_waitlist(event_id, user_id)
            else:
                return {
                    "error": "Event is full for this gender, cannot register",
                    "waitlist_available": True,
                }

        # now = datetime.now(timezone.utc)
        # starts_at = event.starts_at
        # if not starts_at.tzinfo:
        #     starts_at = starts_at.replace(tzinfo=timezone.utc)
        # time_until_event = starts_at - now
        # hours_until_event = time_until_event.total_seconds() / 3600
        # if hours_until_event <= 2:
        #     return {
        #         "error": "Registration is closed for this event (starts within 2 hours)"
        #     }

        # Generate random 4-digit PIN
        pin = "".join(random.choices("0123456789", k=4))

        EventAttendeeRepository.register_for_event(
            {
                "event_id": event_id,
                "user_id": user_id,
                "status": RegistrationStatus.REGISTERED,
                "pin": pin,
            }
        )

        return {"message": "Successfully registered for event"}

    @staticmethod
    def join_event_waitlist(event_id: int, user_id: int):
        """Adds a user to the waitlist for an event."""
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}

        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return {
                "error": "Event is not open for registration for waitlisting"
            }  # Or a different message

        # Double check if user is already registered (should have been caught earlier)
        existing_registration = EventAttendeeRepository.find_by_event_and_user(
            event_id, user_id
        )
        if existing_registration:
            return {
                "error": "You are already registered for this event, cannot join waitlist"
            }

        # Check if user is already on the waitlist
        on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
        if on_waitlist:
            return {"error": "You are already on the waitlist for this event"}
        try:
            EventWaitlistRepository.add_to_waitlist(event_id, user_id)
            return {"message": "Successfully joined the waitlist for the event"}
        except Exception as e:
            # Log the exception e
            return {"error": f"Could not join waitlist: {str(e)}"}

    @staticmethod
    def cancel_registration(event_id: int, user_id: int):
        # Check if user is on waitlist first
        on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
        if on_waitlist:
            removed = EventWaitlistRepository.remove_from_waitlist(event_id, user_id)
            if removed:
                return {"message": "Successfully removed from waitlist"}
            else:
                return {
                    "error": "Failed to remove from waitlist"
                }  # Should not happen if find_by_event_and_user returned entry

        # If not on waitlist, proceed to cancel registration as attendee
        registration = EventAttendeeRepository.find_by_event_and_user(event_id, user_id)
        if not registration:
            return {"error": "You are not registered for this event or on its waitlist"}

        EventAttendeeRepository.delete(event_id, user_id)

        # Attempt to register the first person from the waitlist if a spot opened up
        EventService.process_waitlist_for_event(event_id)

        return {"message": "Successfully cancelled registration"}

    @staticmethod
    def process_waitlist_for_event(event_id: int):
        """Checks if a spot has opened up and registers the first person from the waitlist."""
        event = EventRepository.get_event(event_id)
        if not event or event.status != EventStatus.REGISTRATION_OPEN.value:
            return  # Only process for open events
        attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
        )

        if attendee_count < event.max_capacity:
            first_waitlisted = EventWaitlistRepository.get_first_in_waitlist(event_id)
            if first_waitlisted:
                first_waitlisted_user = UserRepository.find_by_id(
                    first_waitlisted.user_id
                )
                if not first_waitlisted_user:
                    return {
                        "error": f"User with ID {first_waitlisted.user_id} not found"
                    }
                same_gender_count = (
                    EventAttendeeRepository.count_by_event_and_status_and_gender(
                        event_id,
                        [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN],
                        first_waitlisted_user.gender,
                    )
                )

                # get the first waitlisted opposite gender if we have hit capacity
                if same_gender_count >= math.floor(event.max_capacity * 0.6):
                    other_gender = (
                        Gender.MALE
                        if first_waitlisted_user.gender == Gender.FEMALE
                        else Gender.FEMALE
                    )
                    first_waitlisted = (
                        EventWaitlistRepository.get_first_in_waitlist_by_gender(
                            event_id, other_gender
                        )
                    )

                # Attempt to register this user
                pin = "".join(random.choices("0123456789", k=4))
                try:
                    EventAttendeeRepository.register_for_event(
                        {
                            "event_id": event_id,
                            "user_id": first_waitlisted.user_id,
                            "status": RegistrationStatus.REGISTERED,
                            "pin": pin,
                        }
                    )
                    EventWaitlistRepository.remove_from_waitlist(
                        event_id, first_waitlisted.user_id
                    )
                    # Optionally: Send a notification to the user they have been registered.
                    # current_app.logger.info(f"User {first_waitlisted.user_id} registered from waitlist for event {event_id}")
                except Exception as e:
                    # current_app.logger.error(f"Error registering user {first_waitlisted.user_id} from waitlist for event {event_id}: {str(e)}")
                    pass  # Keep them on waitlist if registration fails for some reason

    @staticmethod
    def check_in(event_id: int, user_id: int, pin: str):
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}, 404

        if event.status == EventStatus.COMPLETED.value:
            return {"error": "Cannot check in to a completed event"}, 400

        # Users should ideally only be able to check in if event is Registration Open or In Progress
        if event.status not in [
            EventStatus.REGISTRATION_OPEN.value,
            EventStatus.IN_PROGRESS.value,
        ]:
            return {
                "error": f"Event is not open for check-in (status: {event.status})"
            }, 400

        registration = EventAttendeeRepository.find_by_event_and_user(event_id, user_id)
        if not registration:
            return {"error": "You are not registered for this event"}, 404

        if registration.status == RegistrationStatus.CHECKED_IN:
            return {"error": "You are already checked in for this event"}, 400

        if registration.status != RegistrationStatus.REGISTERED:
            return {
                "error": f"Cannot check in. Your registration status is: {registration.status.name if registration.status else 'Unknown'}"
            }, 400

        if registration.pin != pin:
            return {"error": "Invalid PIN"}, 401  # Unauthorized or 400 Bad Request

        updated_registration = EventAttendeeRepository.update_registration_status(
            registration, RegistrationStatus.CHECKED_IN, datetime.now(timezone.utc)
        )
        if updated_registration:
            return {"message": "Successfully checked in"}, 200
        else:
            # This case should ideally not be hit if update is robust
            return {"error": "Failed to update registration status for check-in"}, 500

    @staticmethod
    def update_event(event_id: int, data: dict, user_id: int):
        event = EventRepository.get_event(event_id)
        if not event:
            return None, {"error": f"Event with ID {event_id} not found"}, 404

        user = UserRepository.find_by_id(user_id)
        if not user:
            return (
                None,
                {"error": "User not found"},
                404,
            )  # Should not happen if JWT is valid

        # Admin can edit any event, Organizer can only edit their own
        if not (
            user.role_id == 3
            or (user.role_id == 2 and str(event.creator_id) == str(user_id))
        ):
            raise UnauthorizedError("You are not authorized to update this event.")

        # Fields that can be updated by admin/organizer
        allowed_fields = [
            "name",
            "description",
            "starts_at",
            "address",
            "max_capacity",
            "price_per_person",
            "status",
            "registration_deadline",
        ]
        update_data = {}

        for field in allowed_fields:
            if field in data:
                value = data[field]
                if field == "starts_at" or field == "registration_deadline":
                    try:
                        update_data[field] = datetime.fromisoformat(
                            value.replace("Z", "+00:00")
                        ).astimezone(timezone.utc)
                    except ValueError:
                        return None, {"error": f"Invalid date format for {field}"}, 400
                elif field == "price_per_person":
                    try:
                        update_data[field] = Decimal(str(value))
                    except ValueError:
                        return None, {"error": f"Invalid format for {field}"}, 400
                elif field == "max_capacity":
                    try:
                        update_data[field] = int(value)
                    except ValueError:
                        return (
                            None,
                            {
                                "error": f"Invalid format for {field}, must be an integer"
                            },
                            400,
                        )
                elif field == "status":
                    if value not in [s.value for s in EventStatus]:
                        return None, {"error": f"Invalid status value: {value}"}, 400
                    update_data[field] = value
                else:
                    update_data[field] = value

        if not update_data:
            return (
                event,
                {"message": "No valid fields provided for update"},
                200,
            )  # Or 400 if no data is bad

        updated_event = EventRepository.update_event(event, update_data)
        return updated_event, {"message": "Event updated successfully"}, 200

    @staticmethod
    def delete_event(event_id: int, user_id: int):
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}, 404

        user = UserRepository.find_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404  # Should not happen

        # Admin can delete any event, Organizer can only delete their own
        if not (
            user.role_id == 3
            or (user.role_id == 2 and str(event.creator_id) == str(user_id))
        ):
            raise UnauthorizedError("You are not authorized to delete this event.")

        if (
            event.status in [EventStatus.IN_PROGRESS.value, EventStatus.COMPLETED.value]
            and user.role_id != 3
        ):
            return {
                "error": f"Event is {event.status} and cannot be deleted by an organizer."
            }, 400

        try:
            EventAttendeeRepository.delete_by_event_id(
                event_id
            )  # Delete attendees first
            EventRepository.delete_event(event)
            return {"message": "Event deleted successfully"}, 200
        except Exception as e:
            return {
                "error": f"An error occurred while deleting the event: {str(e)}"
            }, 500
