from datetime import datetime
from decimal import Decimal
from app.repositories.event_repository import EventRepository
from app.repositories.user_repository import UserRepository
from app.exceptions import UnauthorizedError, MissingFieldsError
from app.models.enums import EventStatus
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
    
    @staticmethod
    def create_event(data, user_id):
        user = UserRepository.find_by_id(user_id)

        if user.role_id not in [2, 3]:  # 2 = Organizer, 3 = Admin
            raise UnauthorizedError()

        required_fields = ['name', 'starts_at', 'address', 'max_capacity', 'price_per_person']
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise MissingFieldsError(missing)

        event = EventRepository.create_event({
            'name': data['name'],
            'description': data.get('description'),
            'creator_id': user_id,
            'starts_at': datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00')),
            'address': data['address'],
            'max_capacity': data['max_capacity'],
            'status': EventStatus.REGISTRATION_OPEN,
            'price_per_person': Decimal(str(data['price_per_person'])),
            'registration_deadline': datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00'))
        })

        return event
