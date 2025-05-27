from app.extensions import db
from sqlalchemy.sql import func

class EventWaitlist(db.Model):
    __tablename__ = "event_waitlists"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    waitlisted_at = db.Column(
        db.TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    event = db.relationship("Event", backref=db.backref("waitlist_entries", lazy="dynamic"))
    user = db.relationship("User", backref=db.backref("waitlist_entries", lazy="dynamic"))

    # Unique constraint to ensure a user can only be on the waitlist for an event once
    __table_args__ = (db.UniqueConstraint("event_id", "user_id", name="uq_event_user_waitlist"),)

    def __repr__(self):
        return f"<EventWaitlist event_id={self.event_id} user_id={self.user_id}>" 