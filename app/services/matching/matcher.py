from typing import List, Dict, Tuple
from app.models.user import User
from app.models.enums import Gender
from app.models.event_speed_date import EventSpeedDate
from app.services.event_attendee_service import EventAttendeeService
import math
from flask import current_app


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
        Find all potential matches for each attendee.
        +-3 years age difference (+-4 years if they don't have the threshold amount of potential dates)
        """
        current_app.logger.info(f"\n\n=== Finding potential dates ===")
        current_app.logger.info(f"Males: {len(males)}, Females: {len(females)}")
        current_app.logger.info(
            f"Initial age difference: {initial_age_difference}, Extended: {extended_age_difference}"
        )
        current_app.logger.info(f"Tables: {num_tables}, Rounds: {num_rounds}\n")

        all_compatible_dates = {}
        id_to_user = {}

        # Initialize matches for all attendees
        for attendee in males + females:
            all_compatible_dates[attendee.id] = []
            id_to_user[attendee.id] = attendee

        # Find matches for each attendee
        for attendee in males + females:
            current_app.logger.info(
                f"\n--- Processing {attendee.first_name} {attendee.last_name} (ID: {attendee.id}) ---"
            )
            current_app.logger.info(
                f"Gender: {attendee.gender}, Age: {attendee.calculate_age()}"
            )

            all_opposite_gender = females if attendee.gender == Gender.MALE else males
            current_app.logger.info(
                f"Total potential matches in opposite gender: {len(all_opposite_gender)}"
            )

            compatible_dates = [
                match
                for match in all_opposite_gender
                if (
                    attendee.church_id != match.church_id
                    or attendee.church_id is None
                    or match.church_id is None
                )
                and (
                    abs(attendee.calculate_age() - match.calculate_age())
                    <= initial_age_difference
                )
            ]
            current_app.logger.info(
                f"\nInitial len of compatible dates (age diff <= {initial_age_difference}): {len(compatible_dates)}"
            )

            # If not enough matches, try extended age range
            num_same_gender = (
                len(females) if attendee.gender == Gender.FEMALE else len(males)
            )
            min_dates_needed = SpeedDateMatcher.min_dates_threshold(
                num_tables, num_rounds, num_same_gender
            )
            current_app.logger.info(f"\nMinimum dates needed: {min_dates_needed}")
            current_app.logger.info(
                f"Current compatible dates: {len(compatible_dates)}"
            )

            if len(compatible_dates) < min_dates_needed:
                current_app.logger.info(
                    f"\nNot enough matches, trying extended age range (<= {extended_age_difference})"
                )
                compatible_dates = [
                    match
                    for match in all_opposite_gender
                    if (
                        attendee.church_id != match.church_id
                        or attendee.church_id is None
                        or match.church_id is None
                    )
                    and (
                        abs(attendee.calculate_age() - match.calculate_age())
                        <= extended_age_difference
                    )
                ]

            if len(compatible_dates) < min_dates_needed:
                current_app.logger.info(
                    f"\nStill not enough matches, trying maximum age range (<= 5)"
                )
                compatible_dates = [
                    match
                    for match in all_opposite_gender
                    if (
                        attendee.church_id != match.church_id
                        or attendee.church_id is None
                        or match.church_id is None
                    )
                    and (abs(attendee.calculate_age() - match.calculate_age()) <= 5)
                ]

            all_compatible_dates[attendee.id] = compatible_dates
            current_app.logger.info(
                f"\nFinal compatible dates for {attendee.first_name} {attendee.last_name}: {len(compatible_dates)}"
            )

        return (all_compatible_dates, id_to_user)

    @staticmethod
    def min_dates_threshold(num_tables, num_rounds, num_same_gender) -> int:
        """
        Threshold that determines whether to extend the age range
        first, calculate the max number of dates that person can have
        then, take the floor of max_dates * .5
        """
        return 6
        if num_same_gender == 0:
            return 0
        max_dates = math.ceil(num_tables * (num_rounds / num_same_gender))
        return math.floor(max_dates * 0.5)

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
            list of all speed dates for the night
        """
        current_app.logger.info(
            f"\n\n\n=== Starting schedule generation for event {event_id} ==="
        )
        current_app.logger.info(f"Requested rounds: {num_rounds}, Tables: {num_tables}")
        current_app.logger.info(f"Total attendees: {len(all_compatible_dates)}\n\n\n")

        event_speed_dates: List[EventSpeedDate] = []
        rounds_completed_per_attendee: Dict[int, int] = {
            k: 0 for k, _ in all_compatible_dates.items()
        }

        for current_round in range(1, num_rounds + 1):
            current_app.logger.info(
                "\n---\nFilling up all tables for ROUND %d\n---\n\n", current_round
            )
            current_app.logger.info(f"Tables to fill: {num_tables}")

            # Log compatible dates state at start of round
            current_app.logger.info("\nCompatible dates at start of round:")
            for user_id, compatible_dates in all_compatible_dates.items():
                user = id_to_user[user_id]
                current_app.logger.info(
                    f"User {user_id} ({user.first_name} {user.last_name}) has {len(compatible_dates)} compatible dates"
                )

            # Sort attendees by number of rounds participated in then by least potential dates
            sorted_attendees = sorted(
                all_compatible_dates,
                key=lambda user_id: (
                    rounds_completed_per_attendee[user_id],
                    len(all_compatible_dates[user_id]),
                ),
            )

            current_app.logger.info(
                "\nSorted attendees by priority (rounds completed, compatible dates):"
            )
            for user_id in sorted_attendees:
                user = id_to_user[user_id]
                current_app.logger.info(
                    f"User {user_id} ({user.first_name} {user.last_name}): "
                    f"{rounds_completed_per_attendee[user_id]} rounds completed, "
                    f"{len(all_compatible_dates[user_id])} compatible dates"
                )

            attendees_seated_this_round = set()
            tables_available_this_round = [
                table_number for table_number in range(1, num_tables + 1)
            ]
            for attendee_id in sorted_attendees:
                attendee = id_to_user[attendee_id]
                if attendee_id in attendees_seated_this_round:
                    current_app.logger.info(
                        f"User {attendee_id} ({attendee.first_name} {attendee.last_name}) already seated this round, skipping"
                    )
                    continue

                current_app.logger.info(
                    f"\nTrying to seat User {attendee_id} ({attendee.first_name} {attendee.last_name})"
                )

                # sort this attendee's compatible dates by fewest rounds participated in then by age difference
                sorted_compatible_dates = sorted(
                    all_compatible_dates[attendee_id],
                    key=lambda user: (
                        rounds_completed_per_attendee[user.id],
                        abs(user.calculate_age() - attendee.calculate_age()),
                    ),
                )

                current_app.logger.info(
                    f"Found {len(sorted_compatible_dates)} potential matches"
                )
                for potential_match in sorted_compatible_dates:
                    current_app.logger.info(
                        f"Potential match: {potential_match.first_name} {potential_match.last_name} "
                        f"(Rounds completed: {rounds_completed_per_attendee[potential_match.id]}, "
                        f"Age diff: {abs(potential_match.calculate_age() - attendee.calculate_age())})"
                    )

                for compatible_date in sorted_compatible_dates:
                    if compatible_date.id not in attendees_seated_this_round:
                        male_id = (
                            attendee_id
                            if attendee.gender == Gender.MALE
                            else compatible_date.id
                        )
                        female_id = (
                            attendee_id
                            if attendee.gender == Gender.FEMALE
                            else compatible_date.id
                        )

                        # set attendee and compatible_date to have a table this round.
                        previous_tables = [
                            esd.table_number
                            for esd in event_speed_dates
                            if esd.round_number == current_round - 1
                            and (esd.male_id == male_id or esd.female_id == female_id)
                            and esd.table_number in tables_available_this_round
                        ]
                        previous_table = previous_tables[0] if previous_tables else None
                        if previous_table:
                            table_number = previous_table
                            current_app.logger.info(
                                f"Reusing previous table {previous_table} for continuity"
                            )
                            tables_available_this_round.remove(previous_table)
                        else:
                            table_number = tables_available_this_round.pop(0)
                        SpeedDateMatcher.assign_table(
                            event_speed_dates,
                            event_id,
                            male_id,
                            female_id,
                            table_number,
                            current_round,
                        )

                        male_user = id_to_user[male_id]
                        female_user = id_to_user[female_id]
                        current_app.logger.info(
                            f"\nAssigned table {table_number} for round {current_round}:"
                            f"\n  Male: {male_user.first_name} {male_user.last_name} (ID: {male_id})"
                            f"\n  Female: {female_user.first_name} {female_user.last_name} (ID: {female_id})"
                        )

                        # track that both these people are now in the current round
                        attendees_seated_this_round.update(
                            [attendee_id, compatible_date.id]
                        )
                        rounds_completed_per_attendee[attendee_id] += 1
                        rounds_completed_per_attendee[compatible_date.id] += 1

                        # remove each other from their compatible dates list
                        if compatible_date in all_compatible_dates[attendee_id]:
                            all_compatible_dates[attendee_id].remove(compatible_date)
                        if attendee in all_compatible_dates[compatible_date.id]:
                            all_compatible_dates[compatible_date.id].remove(attendee)

                        current_app.logger.info(
                            f"\nMale {male_id} with Female {female_id} for Round {current_round} at Table {table_number}"
                        )
                        current_app.logger.info(
                            f"\n{id_to_user[male_id]}{id_to_user[female_id]}"
                        )
                        current_app.logger.info(
                            f"tables now available this round {tables_available_this_round}"
                        )
                        current_app.logger.info(
                            f"Rounds per user id:\n {sorted(rounds_completed_per_attendee.items(), key=lambda item: item[1])}\n"
                        )

                        break  # this attendee has a date this round. moving on to next...

                if len(tables_available_this_round) == 0:
                    current_app.logger.info(
                        "All tables are filled for ROUND %d\n\n", current_round
                    )
                    break

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
            mock_event_id = 13
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
