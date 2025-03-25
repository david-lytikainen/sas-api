from datetime import datetime
from app.extensions import db
from .enums import EventStatus
from decimal import Decimal

class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    starts_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    ends_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(EventStatus), nullable=False)
    price_per_person = db.Column(db.DECIMAL(10, 2), nullable=False)
    registration_deadline = db.Column(db.TIMESTAMP(timezone=True), nullable=False)
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'creator_id': self.creator_id,
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'ends_at': self.ends_at.isoformat() if self.ends_at else None,
            'address': self.address,
            'max_capacity': self.max_capacity,
            'status': self.status.value if self.status else None,
            'price_per_person': str(self.price_per_person) if self.price_per_person else None,
            'registration_deadline': self.registration_deadline.isoformat() if self.registration_deadline else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    