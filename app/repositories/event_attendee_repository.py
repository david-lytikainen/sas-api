from typing import List
from app.extensions import db
from app.models import EventAttendee, User
from app.models.enums import RegistrationStatus

class EventAttendeeRepository:
    @staticmethod
    def find_by_event_id_and_checked_in(event_id: int) -> List[User]:
        return db.session.query(
            User
        ).join(
            EventAttendee, User.id == EventAttendee.user_id
        ).filter(
            EventAttendee.event_id == event_id,
            EventAttendee.status == RegistrationStatus.CHECKED_IN
        ).all()
    
    @staticmethod
    def find_by_event_and_user(event_id: int, user_id: int) -> EventAttendee:
        """Find an attendee registration by event_id and user_id"""
        return EventAttendee.query.filter_by(
            event_id=event_id,
            user_id=user_id
        ).first()
    
    @staticmethod
    def register_for_event(attrs):
         event_attendee = EventAttendee(**attrs)
         db.session.add(event_attendee)
         db.session.commit()
         return event_attendee

    @staticmethod
    def delete(event_id: int, user_id: int):
        registration = EventAttendee.query.filter_by(
            event_id=event_id,
            user_id=user_id
        ).first()
        db.session.delete(registration)
        db.session.commit()
        return registration