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
