from app.repositories.event_repository import EventRepository
from app.repositories.user_repository import UserRepository
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
            return ({'error': 'User not found'}), 404

        events = EventRepository.get_events()
        return [event.to_dict() for event in events]
