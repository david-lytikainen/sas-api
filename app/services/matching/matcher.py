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
        num_active_tables = min(num_tables, (min(num_males, num_females)))
        current_app.logger.info(
            f"Event {event_id}: Generating schedule for {num_males} males, {num_females} females, {num_rounds} rounds, {num_active_tables} active tables."
        )

        male_ids = [m.id for m in males]
        male_participation_count = {male_id: 0 for male_id in male_ids}

        male_table_assignments = {}
        active_males_by_round = {}

        for i, male in enumerate(males):
            table_num = (i % num_active_tables) + 1  # Tables are 1-indexed
            male_table_assignments[male.id] = table_num
            current_app.logger.debug(
                f"Assigning Male {male.id} to fixed Table {table_num}"
            )

        event_speed_dates: List[EventSpeedDate] = []
        met_pairs: Set[Tuple[int, int]] = set()
        female_ids = [f.id for f in females]

        if num_males > num_active_tables:
            male_groups = []
            remaining_males = males.copy()

            while remaining_males:
                group = remaining_males[:num_active_tables]
                male_groups.append(group)
                remaining_males = remaining_males[num_active_tables:]

            if len(male_groups) > 1:
                current_app.logger.info(
                    f"Event {event_id}: Created {len(male_groups)} groups of males for switching"
                )
        else:
            male_groups = [males]

        for round_number in range(1, num_rounds + 1):
            current_app.logger.info(
                f"Event {event_id}: --- Generating Round {round_number} --- "
            )

            if len(male_groups) > 1:
                group_index = (round_number - 1) % len(male_groups)
                active_group = male_groups[group_index]

                if round_number > len(male_groups):
                    high_participation_threshold = (
                        max(male_participation_count.values()) - 1
                    )
                    males_with_high_participation = [
                        m
                        for m in active_group
                        if male_participation_count[m.id]
                        >= high_participation_threshold
                    ]

                    if males_with_high_participation:
                        other_males = [m for m in males if m not in active_group]
                        potential_replacements = sorted(
                            other_males, key=lambda m: male_participation_count[m.id]
                        )

                        for i, high_male in enumerate(males_with_high_participation):
                            if i < len(potential_replacements):
                                replacement = potential_replacements[i]
                                if (
                                    male_participation_count[replacement.id]
                                    < male_participation_count[high_male.id] - 1
                                ):
                                    current_app.logger.debug(
                                        f"Round {round_number}: Replacing Male {high_male.id} (participation={male_participation_count[high_male.id]}) "
                                        f"with Male {replacement.id} (participation={male_participation_count[replacement.id]})"
                                    )
                                    active_group.remove(high_male)
                                    active_group.append(replacement)

                active_males_in_round = active_group
            else:
                active_males_in_round = males

            active_males_by_round[round_number] = [m.id for m in active_males_in_round]
            current_app.logger.info(
                f"Round {round_number}: Active males: {[m.id for m in active_males_in_round]}"
            )

            round_table_assignments = {
                male.id: male_table_assignments[male.id]
                for male in active_males_in_round
            }

            females_available_this_round = list(female_ids)

            female_shift = 0
            if num_females > 0:
                female_shift = (round_number - 1) % num_females

            rotated_available_females = (
                females_available_this_round[female_shift:]
                + females_available_this_round[:female_shift]
            )

            females_seated_this_round = set()
            tables_filled_this_round = 0

            for male_id, table_number in round_table_assignments.items():
                found_partner_for_male = False

                compatible_females = [
                    f.id
                    for f in all_compatible_dates.get(male_id, [])
                    if f.id in rotated_available_females
                    and f.id not in females_seated_this_round
                    and (male_id, f.id) not in met_pairs
                ]

                if compatible_females:
                    female_id = compatible_females[
                        0
                    ]  # Take the first compatible female

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

                    # Increment the male's participation count
                    male_participation_count[male_id] += 1

                if not found_partner_for_male:
                    current_app.logger.warning(
                        f" Round {round_number}: Could not find suitable partner for Male {male_id} at Table {table_number}. Possible reasons: no compatible females left, or all compatible females already met."
                    )

            current_app.logger.info(
                f"Event {event_id}: Finished Round {round_number}, {tables_filled_this_round}/{num_active_tables} tables filled."
            )

        # Log participation counts
        participation_info = sorted(
            [(male_id, count) for male_id, count in male_participation_count.items()],
            key=lambda x: x[1],
            reverse=True,
        )
        current_app.logger.info(f"Event {event_id}: Male participation counts:")
        for male_id, count in participation_info:
            current_app.logger.info(f"  Male {male_id}: {count} dates")

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
