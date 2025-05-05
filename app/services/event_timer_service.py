from app.repositories.event_timer_repository import EventTimerRepository
from app.models.event_timer import EventTimer
from app.services.speed_date_service import SpeedDateService
from datetime import datetime
import pytz
from typing import Dict, Any
from flask import current_app

class EventTimerService:
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
    def pause_round(event_id: int, time_remaining: int | None = None) -> Dict[str, Any]:
        """Pause the current round"""
        # Pass the potentially None time_remaining down to the repository
        timer = EventTimerRepository.pause_round(event_id, time_remaining)
        if not timer:
            # Use the log messages from the repository now
            return {"error": "Timer not found or could not be paused"} 
        
        # Use the actual pause_time_remaining stored by the repo
        actual_remaining = timer.pause_time_remaining if timer.pause_time_remaining is not None else 0
        
        return {
            "timer": timer.to_dict(),
            "message": f"Round {timer.current_round} paused with {actual_remaining} seconds remaining"
        }
    
    @staticmethod
    def resume_round(event_id: int) -> Dict[str, Any]:
        """Resume a paused round"""
        current_app.logger.info(f"EventTimerService: Attempting to resume round for event {event_id}")
        try:
            timer = EventTimerRepository.resume_round(event_id)
            if not timer:
                current_app.logger.warning(f"EventTimerService: Timer not found or could not be resumed for event {event_id}")
                return {"error": "Timer not found or is not paused"}
            
            current_app.logger.info(f"EventTimerService: Round resumed successfully for event {event_id}. Timer state: {timer.to_dict()}")
            return {
                "timer": timer.to_dict(),
                "message": f"Round {timer.current_round} resumed with {timer.pause_time_remaining} seconds remaining"
            }
        except Exception as e:
             current_app.logger.error(f"Error in EventTimerService.resume_round (event {event_id}): {str(e)}", exc_info=True)
             return {"error": "An internal error occurred in the timer service during resume"}
    
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
    def update_duration(event_id: int, round_duration: int = None, break_duration: int = None) -> Dict[str, Any]:
        """Update the round and/or break duration"""
        updates = {}
        messages = []

        if round_duration is not None:
            if round_duration < 30 or round_duration > 900:  # 30s to 15min
                return {"error": "Round duration must be between 30 and 900 seconds"}
            updates['round_duration'] = round_duration
            messages.append(f"Round duration updated to {round_duration} seconds")

        if break_duration is not None:
            if break_duration < 15 or break_duration > 600: # 15s to 10min break
                 return {"error": "Break duration must be between 15 and 600 seconds"}
            updates['break_duration'] = break_duration
            messages.append(f"Break duration updated to {break_duration} seconds")
        
        if not updates:
            return {"error": "No duration values provided to update"}

        timer = EventTimerRepository.update_timer(event_id, **updates)
        if not timer:
            return {"error": "Timer not found"}
        
        return {
            "timer": timer.to_dict(),
            "message": ". ".join(messages)
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
            result["time_remaining"] = timer.pause_time_remaining
        elif timer.round_start_time:
            # Timer has started and is not paused, it must be active
            result["status"] = "active"
            # Determine the correct remaining time to send to the client
            if timer.pause_time_remaining is not None and timer.is_paused is False:
                # It was just resumed, use the paused remaining time
                result["time_remaining"] = timer.pause_time_remaining
            else:
                # It's a normally running timer or just started, send the full duration
                # The client calculates the actual countdown from the round_start_time
                result["time_remaining"] = timer.round_duration
        else:
            # If it's not paused and hasn't started, it's inactive (e.g., between rounds or before start)
            result["status"] = "inactive"
            result["time_remaining"] = 0 # Inactive timer has 0 time remaining displayed
        
        # Clean up pause_time_remaining if the timer is now active and running normally
        # This prevents confusion on subsequent status checks after resuming
        if result["status"] == "active" and timer.pause_time_remaining is not None:
             # We could potentially clear timer.pause_time_remaining in the resume_round repository method instead.
             # For now, just ensure the response reflects the state correctly.
             pass # Keep the logic as is for now, client handles countdown.
             
        return result
