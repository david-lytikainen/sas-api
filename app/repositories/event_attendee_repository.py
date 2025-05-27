from typing import List
from app.extensions import db
from app.models import EventAttendee, User
from app.models.enums import RegistrationStatus, Gender


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
    def count_by_event_id_and_status(
        event_id: int, statuses: List[RegistrationStatus]
    ) -> int:
        """Count attendees for an event with specific registration statuses."""
        return (
            EventAttendee.query.filter(EventAttendee.event_id == event_id)
            .filter(EventAttendee.status.in_(statuses))
            .count()
        )
    
    @staticmethod
    def count_by_event_and_status_and_gender(
        event_id: int, statuses: List[RegistrationStatus], gender: Gender
    ) -> int:
        return (
            db.session.query(EventAttendee)
            .join(User, EventAttendee.user_id == User.id)
            .filter(
                EventAttendee.event_id == event_id,
                EventAttendee.status.in_(statuses),
                User.gender == gender
            ).count()
        )

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

    @staticmethod
    def update_registration_status(registration: EventAttendee, new_status: RegistrationStatus, check_in_date=None):
        """Updates the status and optionally the check_in_date of a registration."""
        if not isinstance(registration, EventAttendee):
            # Or raise an error, or log
            return None 
            
        registration.status = new_status
        if check_in_date and new_status == RegistrationStatus.CHECKED_IN:
            registration.check_in_date = check_in_date
        elif new_status != RegistrationStatus.CHECKED_IN:
            # If status changes from CHECKED_IN to something else, nullify check_in_date
            registration.check_in_date = None 
            
        db.session.add(registration) # Add to session to track changes
        try:
            db.session.commit()
            return registration
        except Exception as e:
            db.session.rollback()
            # Log error e
            # current_app.logger.error(f"Error updating registration status for attendee {registration.id}: {str(e)}")
            return None
