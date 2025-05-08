from typing import List, Dict, Tuple, Set
from app.models.user import User
from app.models.enums import Gender
from app.models.event_speed_date import EventSpeedDate
from app.services.event_attendee_service import EventAttendeeService
import math
from flask import current_app
from app.extensions import db


class SpeedDateMatcher:
    @staticmethod
    def find_all_potential_dates(
        males: List[User],
        females: List[User],
        num_tables: int,
        num_rounds: int,
        initial_age_difference: int = 3,
        extended_age_difference: int = 4,
    ) -> Tuple[Dict[int, List[User]], Dict[int, User]]:
        """
        Find all potential matches for each attendee based on gender and age criteria.
        Returns a tuple: (dict mapping user_id to list of compatible partners, dict mapping user_id to User object)
        """
        all_compatible_dates: Dict[int, List[User]] = {}
        id_to_user: Dict[int, User] = {}

        all_attendees = males + females
        for attendee in all_attendees:
            id_to_user[attendee.id] = attendee
            all_compatible_dates[attendee.id] = []  # Initialize empty list

        # Determine compatibility based on age difference
        for attendee in all_attendees:
            opposite_gender_list = females if attendee.gender == Gender.MALE else males

            # Initial age check
            compatible_partners = [
                partner
                for partner in opposite_gender_list
                if abs(attendee.calculate_age() - partner.calculate_age())
                <= initial_age_difference
            ]

            # Check threshold only if necessary (avoids recalculation)
            if len(compatible_partners) < SpeedDateMatcher.min_dates_threshold(
                num_tables, num_rounds, len(opposite_gender_list)
            ):
                current_app.logger.debug(
                    f"User {attendee.id} has {len(compatible_partners)} compatible partners (initial ≤{initial_age_difference}). Extending range."
                )
                # Extended age check
                compatible_partners = [
                    partner
                    for partner in opposite_gender_list
                    if abs(attendee.calculate_age() - partner.calculate_age())
                    <= extended_age_difference
                ]
                current_app.logger.debug(
                    f"User {attendee.id} now has {len(compatible_partners)} compatible partners (extended ≤{extended_age_difference})."
                )

            all_compatible_dates[attendee.id] = compatible_partners

        return all_compatible_dates, id_to_user

    @staticmethod
    def min_dates_threshold(num_tables, num_rounds, num_opposite_gender) -> int:
        """
        Threshold that determines whether to extend the age range.
        Calculates the theoretical max number of dates someone could have and takes 50%.
        Note: This is a heuristic and might need adjustment based on results.
        """
        if num_opposite_gender == 0:
            return 0  # Avoid division by zero
        max_potential_dates = min(num_rounds, num_opposite_gender)
        threshold = math.floor(max_potential_dates * 0.5)
        return max(1, threshold) if max_potential_dates > 0 else 0

    @staticmethod
    def finalize_all_rounds(
        all_compatible_dates: Dict[int, List[User]],
        id_to_user: Dict[int, User],
        event_id: int,
        num_tables: int,
        num_rounds: int,
    ) -> List[EventSpeedDate]:
        """
        Creates every single speed date for this event.
        Returns:
            List of EventSpeedDate objects representing the schedule.
        """
        males = [user for user in id_to_user.values() if user.gender == Gender.MALE]
        females = [user for user in id_to_user.values() if user.gender == Gender.FEMALE]

        if not males or not females:
            current_app.logger.warning(
                f"Event {event_id}: Cannot generate schedule with zero males or females."
            )
            return []

        num_males = len(males)
        num_females = len(females)
        num_active_tables = min(num_males, num_females, num_tables)

        current_app.logger.info(
            f"Event {event_id}: Generating schedule for {num_males} males, {num_females} females, {num_rounds} rounds, {num_active_tables} active tables."
        )

        # Assign fixed tables to males (up to num_active_tables)
        male_table_assignments: Dict[int, int] = {}
        males_at_tables = males[:num_active_tables]
        for i, male in enumerate(males_at_tables):
            male_table_assignments[male.id] = i + 1  # Tables are 1-indexed
            current_app.logger.debug(f"  Assigning Male {male.id} to Table {i + 1}")

        # --- Scheduling Logic ---
        event_speed_dates: List[EventSpeedDate] = []
        met_pairs: Set[Tuple[int, int]] = set()
        female_ids = [f.id for f in females]

        for round_number in range(1, num_rounds + 1):
            current_app.logger.info(
                f"Event {event_id}: --- Generating Round {round_number} --- "
            )
            # Females available at the start of this round
            females_available_this_round = list(female_ids)
            # Simple cyclic rotation for females for this round
            shift = (round_number - 1) % num_females
            rotated_available_females = (
                females_available_this_round[shift:]
                + females_available_this_round[:shift]
            )

            females_seated_this_round = set()
            tables_filled_this_round = 0

            # Iterate through the males who have fixed tables
            for male_id, table_number in male_table_assignments.items():
                found_partner_for_male = False
                # Try to find a suitable partner from the rotated list
                for female_id in rotated_available_females:
                    # Check if female is already seated this round or if pair already met
                    if (
                        female_id in females_seated_this_round
                        or (male_id, female_id) in met_pairs
                    ):
                        continue

                    male_user = id_to_user[male_id]
                    female_user = id_to_user[female_id]
                    if female_user not in all_compatible_dates.get(male_id, []):
                        current_app.logger.debug(
                            f" Round {round_number}, T{table_number}: Male {male_id} skipping Female {female_id} due to age incompatibility."
                        )
                        continue

                    # --- Assign Date ---
                    current_app.logger.debug(
                        f" Round {round_number}: Assigning Male {male_id} (Table {table_number}) with Female {female_id}"
                    )
                    SpeedDateMatcher.assign_table(
                        event_speed_dates,
                        event_id,
                        male_id,
                        female_id,
                        table_number,  # Use male's fixed table number
                        round_number,
                    )
                    met_pairs.add((male_id, female_id))
                    females_seated_this_round.add(female_id)
                    rotated_available_females.remove(female_id)
                    found_partner_for_male = True
                    tables_filled_this_round += 1
                    break

                if not found_partner_for_male:
                    current_app.logger.warning(
                        f" Round {round_number}: Could not find suitable partner for Male {male_id} at Table {table_number}. Possible reasons: no compatible females left, or all compatible females already met."
                    )

            current_app.logger.info(
                f"Event {event_id}: Finished Round {round_number}, {tables_filled_this_round}/{num_active_tables} tables filled."
            )

        current_app.logger.info(
            f"Event {event_id}: Schedule generation complete. Total dates created: {len(event_speed_dates)}"
        )
        return event_speed_dates

    @staticmethod
    def assign_table(
        event_speed_dates: List[EventSpeedDate],
        event_id: int,
        male_id: int,
        female_id: int,
        table_number: int,
        round_number: int,
    ):
        """
        In place update event_speed_dates, adding the new speed date to it with table_number and round_number
        """
        event_speed_date = EventSpeedDate(
            event_id=event_id,
            male_id=male_id,
            female_id=female_id,
            table_number=table_number,
            round_number=round_number,
        )
        event_speed_dates.append(event_speed_date)

    @staticmethod
    def test():
        from app import create_app

        app = create_app()  # Or however you initialize your Flask app

        with app.app_context():
            mock_event_id = 3
            mock_num_tables = 10
            mock_num_rounds = 10
            attendees = EventAttendeeService.get_checked_in_attendees(mock_event_id)

            males = [user for user in attendees if user.gender == Gender.MALE]
            females = [user for user in attendees if user.gender == Gender.FEMALE]

            (all_compatible_dates, id_to_user) = (
                SpeedDateMatcher.find_all_potential_dates(
                    males, females, mock_num_tables, mock_num_rounds
                )
            )
            event_speed_dates = SpeedDateMatcher.finalize_all_rounds(
                all_compatible_dates,
                id_to_user,
                mock_event_id,
                mock_num_tables,
                mock_num_rounds,
            )


if __name__ == "__main__":
    SpeedDateMatcher.test()
