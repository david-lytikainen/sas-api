from app import db
from .enums import EventStatus

class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    starts_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    ends_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(EventStatus), nullable=False)
    price_per_person = db.Column(db.DECIMAL(10, 2), nullable=False)
    registration_deadline = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    description = db.Column(db.TEXT, nullable=True)
    updated_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())
    