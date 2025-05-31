from app.models.event_speed_date import EventSpeedDate
from app.models.user import User
from app.models.enums import Gender
from app.services.event_attendee_service import EventAttendeeService
from app.services.matching.matcher import SpeedDateMatcher
from app.extensions import db
from flask import current_app
from typing import List, Dict, Any, Tuple
import json


class SpeedDateService:
    @staticmethod
    def generate_schedule(
        event_id: int, num_tables: int, num_rounds: int
    ) -> Tuple[int, int]:
        """
        Generate speed dating schedule for an event

        Args:
            event_id: ID of the event
            num_tables: Number of tables available
            num_rounds: Number of rounds to schedule

        Returns:
            Tuple[int, int]: num_rounds, num_tables
        """
        try:
            EventSpeedDate.query.filter_by(event_id=event_id).delete()
            db.session.commit()

            attendees = EventAttendeeService.get_checked_in_attendees(event_id)
            if not attendees or len(attendees) < 2:
                current_app.logger.warning(
                    f"Not enough attendees checked in for event {event_id} to generate schedule"
                )
                return (-1, -1)

            males = [user for user in attendees if user.gender == Gender.MALE]
            females = [user for user in attendees if user.gender == Gender.FEMALE]
            num_tables_adjusted = min(len(males), len(females)) if num_tables > min(len(males), len(females)) else num_tables

            if not males or not females:
                current_app.logger.warning(
                    f"Need at least one person of each gender to generate schedule for event {event_id}"
                )
                return (-1, -1)

            current_app.logger.info(
                f"Generating schedule for event {event_id} with {len(males)} males and {len(females)} females"
            )

            compatible_dates, id_to_user = SpeedDateMatcher.find_all_potential_dates(
                males, females, num_tables_adjusted, num_rounds
            )
            speed_dates = SpeedDateMatcher.finalize_all_rounds(
                compatible_dates,
                id_to_user,
                event_id,
                num_tables_adjusted,
                num_rounds,
            )

            for speed_date in speed_dates:
                db.session.add(speed_date)

            db.session.commit()
            current_app.logger.info(
                f"Generated {len(speed_dates)} speed dates for event {event_id}"
            )
            return max([esd.round_number for esd in speed_dates]), num_tables_adjusted

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error generating schedule for event {event_id}: {str(e)}"
            )
            return (-1, -1)

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

            # Get user's church name
            user_church = "Other"
            if user.church_id:
                from app.models.church import Church

                church = Church.query.get(user.church_id)
                if church:
                    user_church = church.name

            # Calculate user's age
            user_age = user.calculate_age()

            # Format the schedule with partner details
            schedule = []
            for date in speed_dates:
                partner_id = getattr(date, partner_id_field)
                partner = User.query.get(partner_id)

                if partner:
                    # Get partner's church name
                    partner_church = "Other"
                    if partner.church_id:
                        from app.models.church import Church

                        church = Church.query.get(partner.church_id)
                        if church:
                            partner_church = church.name

                    # Calculate partner's age
                    partner_age = partner.calculate_age()

                    schedule.append(
                        {
                            "round": date.round_number,
                            "table": date.table_number,
                            "partner_id": partner_id,
                            "partner_name": f"{partner.first_name} {partner.last_name}",
                            "partner_age": partner_age,
                            "partner_church": partner_church,
                            "user_age": user_age,
                            "user_church": user_church,
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
