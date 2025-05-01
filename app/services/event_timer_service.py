from app.repositories.event_timer_repository import EventTimerRepository
from app.models.event_timer import EventTimer
from app.services.speed_date_service import SpeedDateService
from datetime import datetime
import pytz
from typing import Dict, Any

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
        """Get the current timer status"""
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
        
        # Calculate time remaining if round is active
        if timer.round_start_time and not timer.is_paused:
            try:
                # Make sure we're comparing timezone-aware datetimes
                current_time = datetime.now(pytz.UTC)
                # Ensure the start time is timezone-aware (should already be from the DB)
                if timer.round_start_time.tzinfo is None:
                    # If it's naive for some reason, make it aware
                    start_time = pytz.UTC.localize(timer.round_start_time)
                else:
                    start_time = timer.round_start_time
                
                elapsed = (current_time - start_time).total_seconds()
                time_remaining = max(0, timer.round_duration - int(elapsed))
                result["time_remaining"] = time_remaining
                result["status"] = "active"
            except Exception as e:
                # Fallback in case of datetime error
                print(f"Error calculating time remaining: {str(e)}")
                result["time_remaining"] = timer.round_duration
                result["status"] = "active"
                
        elif timer.is_paused:
            result["time_remaining"] = timer.pause_time_remaining
            result["status"] = "paused"
        else:
            result["status"] = "inactive"
        
        return result 