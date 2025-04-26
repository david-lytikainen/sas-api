from app.extensions import db
from .enums import RegistrationStatus


class EventAttendee(db.Model):
    __tablename__ = "events_attendees"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.Enum(RegistrationStatus), nullable=False)

    pin = db.Column(db.String(4), nullable=True)
    registration_date = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())
    check_in_date = db.Column(db.TIMESTAMP(timezone=True), nullable=True)
    updated_at = db.Column(
        db.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now()
    )

    def __repr__(self):
        return (
            f"EventAttendee("
            f"id={self.id}, "
            f"event_id={self.event_id}, "
            f"user_id={self.user_id}, "
            f"status={self.status}, "
            f"pin={self.pin}, "
            f"registration_date={self.registration_date}, "
            f"check_in_date={self.check_in_date}, "
            f"updated_at={self.updated_at}, "
            f"created_at={self.created_at}"
            f")"
        )
