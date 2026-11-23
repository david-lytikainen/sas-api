from app.extensions import db
from sqlalchemy import text


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
    enforce_gender_balance = db.Column(
        db.Boolean,
        nullable=False,
        server_default=db.true(),
        default=True,
    )
    price_per_person = db.Column(db.DECIMAL(10, 2), nullable=False)
    registration_deadline = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    num_rounds = db.Column(db.Integer, nullable=True)
    num_tables = db.Column(db.Integer, nullable=True)
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
        attendee_counts = db.session.execute(
            text("""
                select users.gender, count(*) as attendee_count
                from events_attendees
                join users on users.id = events_attendees.user_id
                where events_attendees.event_id = :event_id
                    and events_attendees.status in ('REGISTERED', 'CHECKED_IN')
                group by users.gender
            """),
            {"event_id": self.id},
        ).mappings().all()
        counts_by_gender = {
            row["gender"]: row["attendee_count"] for row in attendee_counts
        }
        registered_attendee_count = sum(counts_by_gender.values())
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "creator_id": self.creator_id,
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "address": self.address,
            "max_capacity": self.max_capacity,
            "status": self.status,
            "enforce_gender_balance": self.enforce_gender_balance,
            "price_per_person": (
                str(self.price_per_person) if self.price_per_person else None
            ),
            "registration_deadline": (
                self.registration_deadline.isoformat()
                if self.registration_deadline
                else None
            ),
            "registered_attendee_count": registered_attendee_count,
            "registered_male_count": counts_by_gender.get("MALE", 0),
            "registered_female_count": counts_by_gender.get("FEMALE", 0),
            "num_rounds": self.num_rounds,
            "num_tables": self.num_tables,
        }
