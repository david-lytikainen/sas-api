from datetime import datetime, timezone
from decimal import Decimal
import random
from app.repositories.event_repository import EventRepository
from app.repositories.user_repository import UserRepository
from app.repositories.event_attendee_repository import EventAttendeeRepository
from app.exceptions import UnauthorizedError, MissingFieldsError
from app.models.enums import EventStatus, RegistrationStatus
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
    def register_for_event(event_id: int, user_id: int):
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}

        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return {"error": "Event is not open for registration"}

        now = datetime.now(timezone.utc)

        starts_at = event.starts_at
        if not starts_at.tzinfo:
            starts_at = starts_at.replace(tzinfo=timezone.utc)

        time_until_event = starts_at - now
        hours_until_event = time_until_event.total_seconds() / 3600

        # if hours_until_event <= 2:
        #     return {
        #         "error": "Registration is closed for this event (starts within 2 hours)"
        #     }

        # Check if user is already registered for this event
        existing_registration = EventAttendeeRepository.find_by_event_and_user(
            event_id, user_id
        )
        if existing_registration:
            return {"error": "You are already registered for this event"}

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
    def cancel_registration(event_id: int, user_id: int):
        EventAttendeeRepository.delete(event_id, user_id)

    @staticmethod
    def update_event(event_id: int, data: dict, user_id: int):
        event = EventRepository.get_event(event_id)
        if not event:
            return None, {"error": f"Event with ID {event_id} not found"}, 404

        user = UserRepository.find_by_id(user_id)
        if not user:
            return None, {"error": "User not found"}, 404 # Should not happen if JWT is valid

        # Admin can edit any event, Organizer can only edit their own
        if not (user.role_id == 3 or (user.role_id == 2 and str(event.creator_id) == str(user_id))):
            raise UnauthorizedError("You are not authorized to update this event.")

        # Fields that can be updated by admin/organizer
        allowed_fields = ['name', 'description', 'starts_at', 'address', 'max_capacity', 'price_per_person', 'status', 'registration_deadline']
        update_data = {}

        for field in allowed_fields:
            if field in data:
                value = data[field]
                if field == 'starts_at' or field == 'registration_deadline':
                    try:
                        update_data[field] = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
                    except ValueError:
                        return None, {"error": f"Invalid date format for {field}"}, 400
                elif field == 'price_per_person':
                    try:
                        update_data[field] = Decimal(str(value))
                    except ValueError:
                        return None, {"error": f"Invalid format for {field}"}, 400
                elif field == 'max_capacity':
                    try:
                        update_data[field] = int(value)
                    except ValueError:
                         return None, {"error": f"Invalid format for {field}, must be an integer"}, 400
                elif field == 'status':
                    if value not in [s.value for s in EventStatus]:
                        return None, {"error": f"Invalid status value: {value}"}, 400
                    update_data[field] = value
                else:
                    update_data[field] = value
        
        if not update_data:
            return event, {"message": "No valid fields provided for update"}, 200 # Or 400 if no data is bad

        updated_event = EventRepository.update_event(event, update_data)
        return updated_event, {"message": "Event updated successfully"}, 200

    @staticmethod
    def delete_event(event_id: int, user_id: int):
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}, 404

        user = UserRepository.find_by_id(user_id)
        if not user:
             return {"error": "User not found"}, 404 # Should not happen

        # Admin can delete any event, Organizer can only delete their own
        if not (user.role_id == 3 or (user.role_id == 2 and str(event.creator_id) == str(user_id))):
            raise UnauthorizedError("You are not authorized to delete this event.")

        if event.status in [EventStatus.IN_PROGRESS.value, EventStatus.COMPLETED.value] and user.role_id != 3:
            return {"error": f"Event is {event.status} and cannot be deleted by an organizer."}, 400

        try:
            EventAttendeeRepository.delete_by_event_id(event_id) # Delete attendees first
            EventRepository.delete_event(event)
            return {"message": "Event deleted successfully"}, 200
        except Exception as e:
            return {"error": f"An error occurred while deleting the event: {str(e)}"}, 500
