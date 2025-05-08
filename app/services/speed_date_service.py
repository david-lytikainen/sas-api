from app.models.event_speed_date import EventSpeedDate
from app.models.user import User
from app.models.enums import Gender
from app.services.event_attendee_service import EventAttendeeService
from app.services.matching.matcher import SpeedDateMatcher
from app.extensions import db
from flask import current_app
from typing import List, Dict, Any
import json


class SpeedDateService:
    @staticmethod
    def generate_schedule(
        event_id: int, num_tables: int = 10, num_rounds: int = 10
    ) -> bool:
        """
        Generate speed dating schedule for an event

        Args:
            event_id: ID of the event
            num_tables: Number of tables available
            num_rounds: Number of rounds to schedule

        Returns:
            bool: True if schedule was generated successfully
        """
        try:
            # Delete any existing schedule for this event
            EventSpeedDate.query.filter_by(event_id=event_id).delete()
            db.session.commit()

            # Get checked-in attendees
            attendees = EventAttendeeService.get_checked_in_attendees(event_id)

            if not attendees or len(attendees) < 2:
                current_app.logger.warning(
                    f"Not enough attendees checked in for event {event_id} to generate schedule"
                )
                return False

            # Split attendees by gender
            males = [user for user in attendees if user.gender == Gender.MALE]
            females = [user for user in attendees if user.gender == Gender.FEMALE]

            # Make sure we have at least one person of each gender
            if not males or not females:
                current_app.logger.warning(
                    f"Need at least one person of each gender to generate schedule for event {event_id}"
                )
                return False

            current_app.logger.info(
                f"Generating schedule for event {event_id} with {len(males)} males and {len(females)} females"
            )

            # Calculate appropriate number of tables and rounds based on attendance
            calculated_num_tables = min(num_tables, min(len(males), len(females)))
            calculated_num_rounds = min(num_rounds, max(len(males), len(females)))

            # Find compatible dates and generate schedule
            compatible_dates, id_to_user = SpeedDateMatcher.find_all_potential_dates(
                males, females, calculated_num_tables, calculated_num_rounds
            )

            speed_dates = SpeedDateMatcher.finalize_all_rounds(
                compatible_dates,
                id_to_user,
                event_id,
                calculated_num_tables,
                calculated_num_rounds,
            )

            # Save to database
            for speed_date in speed_dates:
                db.session.add(speed_date)

            db.session.commit()
            current_app.logger.info(
                f"Generated {len(speed_dates)} speed dates for event {event_id}"
            )
            return True

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error generating schedule for event {event_id}: {str(e)}"
            )
            return False

    @staticmethod
    def get_schedule_for_attendee(event_id: int, user_id: int) -> List[Dict[str, Any]]:
        """
        Get the speed dating schedule for a specific attendee

        Args:
            event_id: ID of the event
            user_id: ID of the user

        Returns:
            List of scheduled dates with details
        """
        try:
            # Determine user's gender
            user = User.query.get(user_id)
            if not user:
                return []

            # Query based on gender
            if user.gender == Gender.MALE:
                # For males, look at the male_id field
                speed_dates = (
                    EventSpeedDate.query.filter_by(event_id=event_id, male_id=user_id)
                    .order_by(EventSpeedDate.round_number)
                    .all()
                )
                partner_id_field = "female_id"
            else:
                # For females, look at the female_id field
                speed_dates = (
                    EventSpeedDate.query.filter_by(event_id=event_id, female_id=user_id)
                    .order_by(EventSpeedDate.round_number)
                    .all()
                )
                partner_id_field = "male_id"

            # Format the schedule with partner details
            schedule = []
            for date in speed_dates:
                partner_id = getattr(date, partner_id_field)
                partner = User.query.get(partner_id)

                if partner:
                    schedule.append(
                        {
                            "round": date.round_number,
                            "table": date.table_number,
                            "partner_id": partner_id,
                            "partner_name": f"{partner.first_name} {partner.last_name}",
                            "partner_age": partner.calculate_age(),
                            "event_speed_date_id": date.id,
                        }
                    )

            return schedule

        except Exception as e:
            current_app.logger.error(
                f"Error getting schedule for user {user_id} in event {event_id}: {str(e)}"
            )
            return []

    @staticmethod
    def get_all_schedules(event_id: int) -> Dict[int, List[Dict[str, Any]]]:
        """
        Get speed dating schedules for all attendees of an event

        Args:
            event_id: ID of the event

        Returns:
            Dict mapping user_id to their schedule
        """
        try:
            # Get all checked-in attendees
            attendees = EventAttendeeService.get_checked_in_attendees(event_id)

            # Get schedule for each attendee
            schedules = {}
            for attendee in attendees:
                schedule = SpeedDateService.get_schedule_for_attendee(
                    event_id, attendee.id
                )
                schedules[attendee.id] = schedule

            return schedules

        except Exception as e:
            current_app.logger.error(
                f"Error getting all schedules for event {event_id}: {str(e)}"
            )
            return {}
