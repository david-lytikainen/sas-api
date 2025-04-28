from app.extensions import db
from app.models.event_timer import EventTimer
from datetime import datetime
import pytz

class EventTimerRepository:
    @staticmethod
    def get_timer(event_id: int) -> EventTimer:
        """Get the timer for a specific event"""
        return EventTimer.query.filter_by(event_id=event_id).first()
    
    @staticmethod
    def create_timer(event_id: int, round_duration: int = 180) -> EventTimer:
        """Create a new timer for an event"""
        timer = EventTimer(
            event_id=event_id,
            current_round=1,
            round_duration=round_duration
        )
        db.session.add(timer)
        db.session.commit()
        return timer
    
    @staticmethod
    def update_timer(event_id: int, **kwargs) -> EventTimer:
        """Update timer attributes"""
        timer = EventTimerRepository.get_timer(event_id)
        if timer:
            for key, value in kwargs.items():
                if hasattr(timer, key):
                    setattr(timer, key, value)
            db.session.commit()
        return timer
    
    @staticmethod
    def start_round(event_id: int, round_number: int = None) -> EventTimer:
        """Start or restart a round"""
        timer = EventTimerRepository.get_timer(event_id)
        if timer:
            if round_number:
                timer.current_round = round_number
            timer.round_start_time = datetime.now(pytz.UTC)
            timer.is_paused = False
            timer.pause_time_remaining = None
            db.session.commit()
        return timer
    
    @staticmethod
    def pause_round(event_id: int, time_remaining: int) -> EventTimer:
        """Pause the current round"""
        timer = EventTimerRepository.get_timer(event_id)
        if timer:
            timer.is_paused = True
            timer.pause_time_remaining = time_remaining
            db.session.commit()
        return timer
    
    @staticmethod
    def resume_round(event_id: int) -> EventTimer:
        """Resume a paused round"""
        timer = EventTimerRepository.get_timer(event_id)
        if timer and timer.is_paused:
            timer.is_paused = False
            timer.round_start_time = datetime.now(pytz.UTC)
            # Keep the pause_time_remaining to know how much time is left
            db.session.commit()
        return timer
    
    @staticmethod
    def next_round(event_id: int) -> EventTimer:
        """Advance to the next round"""
        timer = EventTimerRepository.get_timer(event_id)
        if timer:
            timer.current_round += 1
            timer.round_start_time = datetime.now(pytz.UTC)
            timer.is_paused = False
            timer.pause_time_remaining = None
            db.session.commit()
        return timer 