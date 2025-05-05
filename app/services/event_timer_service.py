from app.repositories.event_timer_repository import EventTimerRepository
from app.models.event_timer import EventTimer
from app.services.speed_date_service import SpeedDateService
from datetime import datetime
import pytz
from typing import Dict, Any
from flask import current_app

# Import SSE utilities
from app.sse_utils import announcer, format_sse 

class EventTimerService:
    @staticmethod
    def initialize_timer(event_id: int, round_duration: int = 180) -> Dict[str, Any]:
        """Initialize a timer for an event"""
        # Check if timer already exists
        timer = EventTimerRepository.get_timer(event_id)
        if not timer:
            timer = EventTimerRepository.create_timer(event_id, round_duration)
        
        return timer.to_dict()
    
    @staticmethod
    def start_round(event_id: int, round_number: int = None) -> Dict[str, Any]:
        """Start a specific round or the current round"""
        timer = EventTimerRepository.start_round(event_id, round_number)
        if not timer:
            # Create a timer if it doesn't exist
            timer = EventTimerRepository.create_timer(event_id)
            timer = EventTimerRepository.start_round(event_id, round_number)
        
        return {
            "timer": timer.to_dict(),
            "message": f"Round {timer.current_round} started"
        }
    
    @staticmethod
    def pause_round(event_id: int, time_remaining: int) -> Dict[str, Any]:
        """Pause the current round"""
        timer = EventTimerRepository.pause_round(event_id, time_remaining)
        if not timer:
            return {"error": "Timer not found"}
        
        return {
            "timer": timer.to_dict(),
            "message": f"Round {timer.current_round} paused with {time_remaining} seconds remaining"
        }
    
    @staticmethod
    def resume_round(event_id: int) -> Dict[str, Any]:
        """Resume a paused round"""
        timer = EventTimerRepository.resume_round(event_id)
        if not timer:
            return {"error": "Timer not found"}
        
        return {
            "timer": timer.to_dict(),
            "message": f"Round {timer.current_round} resumed with {timer.pause_time_remaining} seconds remaining"
        }
    
    @staticmethod
    def next_round(event_id: int, max_rounds: int = 10) -> Dict[str, Any]:
        """Advance to the next round"""
        timer = EventTimerRepository.get_timer(event_id)
        if not timer:
            return {"error": "Timer not found"}
        
        # Check if we're already at the maximum round
        if timer.current_round >= max_rounds:
            return {
                "timer": timer.to_dict(),
                "message": "All rounds completed",
                "complete": True
            }
        
        timer = EventTimerRepository.next_round(event_id)
        
        return {
            "timer": timer.to_dict(),
            "message": f"Advanced to round {timer.current_round}"
        }
    
    @staticmethod
    def update_duration(event_id: int, round_duration: int) -> Dict[str, Any]:
        """Update the round duration"""
        if round_duration < 30 or round_duration > 900:  # 30s to 15min
            return {"error": "Round duration must be between 30 and 900 seconds"}
        
        timer = EventTimerRepository.update_timer(event_id, round_duration=round_duration)
        if not timer:
            return {"error": "Timer not found"}
        
        return {
            "timer": timer.to_dict(),
            "message": f"Round duration updated to {round_duration} seconds"
        }
    
    @staticmethod
    def get_timer_status(event_id: int) -> Dict[str, Any]:
        """Get the current timer status from the database"""
        timer = EventTimerRepository.get_timer(event_id)
        if not timer:
            # We don't have a timer yet
            return {
                "has_timer": False,
                "message": "Timer not initialized"
            }
        
        result = {
            "has_timer": True,
            "timer": timer.to_dict(),
            "message": f"Round {timer.current_round}"
        }
        
        # Determine status based on persisted state
        if timer.is_paused:
            result["status"] = "paused"
            # Return the time remaining when it was paused
            result["time_remaining"] = timer.pause_time_remaining
        elif timer.round_start_time:
            result["status"] = "active"
            # Indicate the full duration; client will calculate remaining based on start time
            result["time_remaining"] = timer.round_duration 
            # If resuming from pause, client needs this info
            if timer.pause_time_remaining is not None:
                # This signals to the client it was resumed and what time remained
                 result["time_remaining"] = timer.pause_time_remaining 
        else:
            result["status"] = "inactive"
            result["time_remaining"] = timer.round_duration # Or 0, depending on desired inactive display
        
        return result
