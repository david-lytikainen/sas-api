from app.extensions import db
from app.models.event_timer import EventTimer
from app.repositories.event_repository import EventRepository
from datetime import datetime, timezone, timedelta
import pytz
from flask import current_app  # Import current_app for logging


class EventTimerRepository:
    @staticmethod
    def get_timer(event_id: int) -> EventTimer:
        """Get the timer for a specific event"""
        return EventTimer.query.filter_by(event_id=event_id).first()

    @staticmethod
    def create_timer(event_id: int, round_duration: int = 180) -> EventTimer:
        """Create a new timer for an event"""
        final_round = EventRepository.get_event(event_id).num_rounds
        timer = EventTimer(
            event_id=event_id,
            current_round=1,
            final_round=final_round,
            round_duration=round_duration,
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
    def start_round(event_id: int, round_number: int = None) -> EventTimer | None:
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
    def end_round(event_id: int):
        timer = EventTimerRepository.get_timer(event_id)
        if timer and timer.round_start_time:
            now = datetime.now(pytz.UTC)
            timer.round_start_time = now - timedelta(seconds=timer.round_duration)
            db.session.commit()
        return timer

    @staticmethod
    def pause_round(
        event_id: int, time_remaining: int | None = None
    ) -> EventTimer | None:
        """Pause the current round"""
        timer = EventTimerRepository.get_timer(event_id)
        if not timer or timer.is_paused:
            current_app.logger.warning(
                f"Repository: Attempted to pause non-existent or already paused timer for event {event_id}"
            )
            return None

        # Calculate time_remaining if not provided
        calculated_remaining = None
        if time_remaining is None:
            if timer.round_start_time:
                now = datetime.now(timezone.utc)
                elapsed = (now - timer.round_start_time).total_seconds()
                calculated_remaining = max(0, timer.round_duration - int(elapsed))
                current_app.logger.info(
                    f"Repository: No time_remaining provided for pause (event {event_id}). Calculated: {calculated_remaining}s"
                )
                time_remaining = calculated_remaining
            else:
                current_app.logger.warning(
                    f"Repository: Cannot pause timer for event {event_id}. time_remaining not provided and round_start_time is null."
                )
                return None

        current_app.logger.info(
            f"Repository: Attempting to pause timer for event {event_id} with effective time_remaining {time_remaining}"
        )

        try:
            timer.is_paused = True
            timer.pause_time_remaining = time_remaining
            timer.round_start_time = None
            db.session.commit()
            current_app.logger.info(
                f"Repository: Timer paused successfully for event {event_id}"
            )
            return timer
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Repository: Error pausing timer for event {event_id}: {str(e)}",
                exc_info=True,
            )
            return None

    @staticmethod
    def resume_round(event_id: int) -> EventTimer | None:
        """Resume a paused round"""
        current_app.logger.info(
            f"Repository: Attempting to resume timer for event {event_id}"
        )
        timer = EventTimerRepository.get_timer(event_id)
        if timer and timer.is_paused:
            try:
                current_app.logger.info(
                    f"Found paused timer {timer.id}. Setting is_paused=False, updating round_start_time."
                )
                timer.is_paused = False

                # Calculate the start time based on pause_time_remaining
                if timer.pause_time_remaining is not None:
                    now = datetime.now(pytz.UTC)
                    elapsed_seconds = timer.round_duration - timer.pause_time_remaining
                    # Set round_start_time to be elapsed_seconds before now
                    timer.round_start_time = now - timedelta(seconds=elapsed_seconds)
                else:
                    # Fallback to current time if pause_time_remaining is None
                    timer.round_start_time = datetime.now(pytz.UTC)

                # Keep the pause_time_remaining to know how much time is left
                current_app.logger.info("Committing resume changes to DB...")
                db.session.commit()
                current_app.logger.info("Commit successful.")
            except Exception as e:
                current_app.logger.error(
                    f"DATABASE ERROR during resume_round (event {event_id}): {str(e)}",
                    exc_info=True,
                )
                db.session.rollback()  # Rollback on error
                return None  # Indicate failure
        elif timer:
            current_app.logger.warning(
                f"Timer {timer.id} for event {event_id} found but was not paused."
            )
            return None
        else:
            current_app.logger.warning(
                f"Timer not found for event {event_id} in resume_round."
            )
            return None  # Indicate failure
        return timer

    @staticmethod
    def next_round(event_id: int) -> EventTimer | None:
        """Advance to the next round"""
        timer = EventTimerRepository.get_timer(event_id)
        if timer:
            timer.current_round += 1
            timer.round_start_time = datetime.now(pytz.UTC)
            timer.is_paused = False
            timer.pause_time_remaining = None
            db.session.commit()
        return timer

    @staticmethod
    def delete_timer(event_id: int) -> bool:
        """Delete the timer for a specific event"""
        try:
            timer = EventTimerRepository.get_timer(event_id)
            if timer:
                db.session.delete(timer)
                db.session.commit()
                current_app.logger.info(
                    f"Successfully deleted timer for event {event_id}"
                )
                return True
            else:
                current_app.logger.warning(
                    f"No timer found to delete for event {event_id}"
                )
                return False
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error deleting timer for event {event_id}: {str(e)}", exc_info=True
            )
            return False
