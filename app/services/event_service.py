from app.repositories.event_repository import EventRepository
from app.models import Event
from typing import List

class EventService:
    @staticmethod
    def get_events() -> List[Event]:
        return EventRepository.get_events()
