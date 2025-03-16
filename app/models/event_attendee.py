from app.extensions import db
from .enums import RegistrationStatus

class EventAttendee(db.Model):
    __tablename__ = 'events_attendees'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.Enum(RegistrationStatus), nullable=False)
    registration_date = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())
    check_in_date = db.Column(db.TIMESTAMP(timezone=True), nullable=True)
    updated_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())
    