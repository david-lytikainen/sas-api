from app.repositories.event_timer_repository import EventTimerRepository
from app.models.event_timer import EventTimer
from app.services.speed_date_service import SpeedDateService
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any
from flask import current_app


class EventTimerService:
    @staticmethod
    def start_round(event_id: int, round_number: int = None) -> Dict[str, Any]:
        """Start a specific round or the current round"""
        timer = EventTimerRepository.start_round(event_id, round_number)
        if not timer:
            timer = EventTimerRepository.create_timer(event_id)
            timer = EventTimerRepository.start_round(event_id, round_number)

        return {
            "timer": timer.to_dict(),
            "message": f"Round {timer.current_round} started",
        }

    @staticmethod
    def end_round(event_id: int):
        return EventTimerRepository.end_round(event_id)

    @staticmethod
    def pause_round(event_id: int, time_remaining: int | None = None) -> Dict[str, Any]:
        """Pause the current round"""
        timer = EventTimerRepository.pause_round(event_id, time_remaining)
        if not timer:
            return {"error": "Timer not found or could not be paused"}

        actual_remaining = (
            timer.pause_time_remaining if timer.pause_time_remaining is not None else 0
        )

        return {
            "timer": timer.to_dict(),
            "message": f"Round {timer.current_round} paused with {actual_remaining} seconds remaining",
        }

    @staticmethod
    def resume_round(event_id: int) -> Dict[str, Any]:
        """Resume a paused round"""
        current_app.logger.info(
            f"EventTimerService: Attempting to resume round for event {event_id}"
        )
        try:
            timer = EventTimerRepository.resume_round(event_id)
            if not timer:
                current_app.logger.warning(
                    f"EventTimerService: Timer not found or could not be resumed for event {event_id}"
                )
                return {"error": "Timer not found or is not paused"}

            current_app.logger.info(
                f"EventTimerService: Round resumed successfully for event {event_id}. Timer state: {timer.to_dict()}"
            )
            return {
                "timer": timer.to_dict(),
                "message": f"Round {timer.current_round} resumed with {timer.pause_time_remaining} seconds remaining",
            }
        except Exception as e:
            current_app.logger.error(
                f"Error in EventTimerService.resume_round (event {event_id}): {str(e)}",
                exc_info=True,
            )
            return {
                "error": "An internal error occurred in the timer service during resume"
            }

    @staticmethod
    def next_round(event_id: int) -> Dict[str, Any]:
        """Advance to the next round"""
        timer = EventTimerRepository.get_timer(event_id)
        if not timer:
            return {"error": "Timer not found"}

        if timer.current_round >= timer.final_round:
            return {
                "timer": timer.to_dict(),
                "message": "All rounds completed",
                "complete": True,
            }

        timer = EventTimerRepository.next_round(event_id)

        return {
            "timer": timer.to_dict(),
            "message": f"Advanced to round {timer.current_round}",
        }

    @staticmethod
    def update_duration(
        event_id: int, round_duration: int = None, break_duration: int = None
    ) -> Dict[str, Any]:
        """Update the round and/or break duration"""
        updates = {}
        messages = []

        if round_duration is not None:
            if round_duration < 30 or round_duration > 900:  # 30s to 15min
                return {"error": "Round duration must be between 30 and 900 seconds"}
            updates["round_duration"] = round_duration
            messages.append(f"Round duration updated to {round_duration} seconds")

        if break_duration is not None:
            if break_duration < 15 or break_duration > 600:  # 15s to 10min break
                return {"error": "Break duration must be between 15 and 600 seconds"}
            updates["break_duration"] = break_duration
            messages.append(f"Break duration updated to {break_duration} seconds")

        if not updates:
            return {"error": "No duration values provided to update"}

        timer = EventTimerRepository.update_timer(event_id, **updates)
        if not timer:
            return {"error": "Timer not found"}

        return {"timer": timer.to_dict(), "message": ". ".join(messages)}

    @staticmethod
    def get_timer_status(event_id: int) -> Dict[str, Any]:
        """Get the current timer status from the database"""
        timer = EventTimerRepository.get_timer(event_id)
        if not timer:
            return {"has_timer": False, "message": "Timer not initialized"}

        result = {
            "has_timer": True,
            "timer": timer.to_dict(),
            "message": f"Round {timer.current_round}",
        }

        now = datetime.now(pytz.UTC)
        isRoundEnded = (
            ((now - timer.round_start_time).total_seconds() >= timer.round_duration)
            if timer.round_start_time
            else False
        )
        if timer.is_paused:  # paused
            result["status"] = "paused"
            result["time_remaining"] = timer.pause_time_remaining
        elif (
            timer.current_round >= timer.final_round
            and not timer.is_paused
            and isRoundEnded
        ):  # ended
            result["status"] = "ended"
        elif isRoundEnded:
            result["status"] = "break_time"
        elif timer.round_start_time:  # active
            result["status"] = "active"
            if timer.pause_time_remaining is not None and timer.is_paused is False:
                result["time_remaining"] = timer.pause_time_remaining
            else:
                result["time_remaining"] = timer.round_duration
        else:  # inactive
            result["status"] = "inactive"
            result["time_remaining"] = 0

        return result

    @staticmethod
    def delete_timer(event_id: int) -> bool:
        return EventTimerRepository.delete_timer(event_id)

    @staticmethod
    def create_timer(event_id: int):
        return EventTimerRepository.create_timer(event_id)
