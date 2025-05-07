from app.extensions import db
from datetime import datetime

class EventTimer(db.Model):
    __tablename__ = 'event_timers'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    current_round = db.Column(db.Integer, nullable=False, default=1)
    round_duration = db.Column(db.Integer, nullable=False, default=180)  # Duration in seconds
    round_start_time = db.Column(db.TIMESTAMP(timezone=True), nullable=True)
    is_paused = db.Column(db.Boolean, nullable=False, default=False)
    pause_time_remaining = db.Column(db.Integer, nullable=True)  # Seconds remaining when paused
    break_duration = db.Column(db.Integer, nullable=False, default=90) # Default break duration in seconds
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    
    # Define relationship
    event = db.relationship('Event', backref=db.backref('timer', uselist=False))
    
    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'current_round': self.current_round,
            'round_duration': self.round_duration,
            'round_start_time': self.round_start_time.isoformat() if self.round_start_time else None,
            'is_paused': self.is_paused,
            'pause_time_remaining': self.pause_time_remaining,
            'break_duration': self.break_duration
        } 