from app.extensions import db
from app.models.event_waitlist import EventWaitlist
from app.models.user import User  # For type hinting or joining if needed
from typing import List, Optional
from app.models.enums import Gender


class EventWaitlistRepository:
    @staticmethod
    def add_to_waitlist(event_id: int, user_id: int) -> EventWaitlist:
        """Adds a user to the waitlist for a specific event."""
        waitlist_entry = EventWaitlist(event_id=event_id, user_id=user_id)
        db.session.add(waitlist_entry)
        db.session.commit()
        return waitlist_entry

    @staticmethod
    def find_by_event_and_user(event_id: int, user_id: int) -> Optional[EventWaitlist]:
        """Checks if a user is already on the waitlist for an event."""
        return EventWaitlist.query.filter_by(event_id=event_id, user_id=user_id).first()

    @staticmethod
    def get_waitlist_for_event(event_id: int) -> List[EventWaitlist]:
        """Gets all users on the waitlist for a specific event, ordered by when they joined."""
        return (
            EventWaitlist.query.filter_by(event_id=event_id)
            .order_by(EventWaitlist.waitlisted_at.asc())
            .all()
        )

    @staticmethod
    def count_by_event_id(event_id: int) -> int:
        """Counts the number of users on the waitlist for a specific event."""
        return EventWaitlist.query.filter_by(event_id=event_id).count()

    @staticmethod
    def remove_from_waitlist(event_id: int, user_id: int) -> bool:
        """Removes a user from the waitlist for a specific event."""
        entry = EventWaitlist.query.filter_by(
            event_id=event_id, user_id=user_id
        ).first()
        if entry:
            db.session.delete(entry)
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_first_in_waitlist(event_id: int) -> Optional[EventWaitlist]:
        """Gets the first user in the waitlist for an event (oldest entry)."""
        return (
            EventWaitlist.query.filter_by(event_id=event_id)
            .order_by(EventWaitlist.waitlisted_at.asc())
            .first()
        )

    @staticmethod
    def get_first_in_waitlist_by_gender(event_id: int, gender: Gender):
        return (
            db.session.query(EventWaitlist)
            .join(User, EventWaitlist.user_id == User.id)
            .filter(EventWaitlist.event_id == event_id, User.gender == gender)
            .order_by(EventWaitlist.waitlisted_at.asc())
            .first()
        )
