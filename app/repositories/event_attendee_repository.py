from typing import List
from app.extensions import db
from app.models import EventAttendee, User
from app.models.enums import RegistrationStatus


class EventAttendeeRepository:
    @staticmethod
    def find_by_event_id_and_checked_in(event_id: int) -> List[User]:
        return (
            db.session.query(User)
            .join(EventAttendee, User.id == EventAttendee.user_id)
            .filter(
                EventAttendee.event_id == event_id,
                EventAttendee.status == RegistrationStatus.CHECKED_IN,
            )
            .all()
        )

    @staticmethod
    def find_by_event_and_user(event_id: int, user_id: int) -> EventAttendee:
        """Find an attendee registration by event_id and user_id"""
        return EventAttendee.query.filter_by(event_id=event_id, user_id=user_id).first()

    @staticmethod
    def register_for_event(attrs):
        event_attendee = EventAttendee(**attrs)
        db.session.add(event_attendee)
        db.session.commit()
        return event_attendee

    @staticmethod
    def delete(event_id: int, user_id: int):
        registration = EventAttendee.query.filter_by(
            event_id=event_id, user_id=user_id
        ).first()
        if registration:
            db.session.delete(registration)
            db.session.commit()
        return registration

    @staticmethod
    def delete_by_event_id(event_id: int):
        """Deletes all attendee registrations for a given event_id."""
        try:
            num_deleted = EventAttendee.query.filter_by(event_id=event_id).delete()
            db.session.commit()
            return num_deleted
        except Exception as e:
            db.session.rollback()
            # Log error e, for example: current_app.logger.error(f"Error deleting attendees for event {event_id}: {str(e)}")
            raise e  # Re-raise the exception to be handled by the service/route
