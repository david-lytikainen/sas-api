from app.repositories.event_attendee_repository import EventAttendeeRepository
from app.models import User
from typing import List

class EventAttendeeService:
    @staticmethod
    def get_checked_in_attendees(event_id: int) -> List[User]:
        return EventAttendeeRepository.find_by_event_id_and_checked_in(event_id)
