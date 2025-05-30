from app.extensions import db
from .enums import RegistrationStatus


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    starts_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
    )
    price_per_person = db.Column(db.DECIMAL(10, 2), nullable=False)
    registration_deadline = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    num_rounds = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now()
    )
    updated_at = db.Column(
        db.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    def to_dict(self):
        from .event_attendee import EventAttendee

        registered_attendee_count = (
            EventAttendee.query.filter(EventAttendee.event_id == self.id)
            .filter(
                EventAttendee.status.in_(
                    [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
                )
            )
            .count()
        )
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "creator_id": self.creator_id,
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "address": self.address,
            "max_capacity": self.max_capacity,
            "status": self.status,
            "price_per_person": (
                str(self.price_per_person) if self.price_per_person else None
            ),
            "registration_deadline": (
                self.registration_deadline.isoformat()
                if self.registration_deadline
                else None
            ),
            "registered_attendee_count": registered_attendee_count,
        }
