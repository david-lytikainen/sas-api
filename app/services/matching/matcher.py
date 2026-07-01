from typing import List, Dict, Tuple
from app.models.user import User
from app.models.enums import Gender
from app.models.event_speed_date import EventSpeedDate
import math
from flask import current_app
from sqlalchemy import or_


class SpeedDateMatcher:
    @staticmethod
    def find_all_potential_dates(
        males: List[User],
        females: List[User],
        num_tables: int,
        num_rounds: int,
    ) -> Tuple[Dict[int, List[User]], Dict[int, User]]:
        current_app.logger.info("\n\n=== Finding potential dates ===")
        current_app.logger.info(f"Males: {len(males)}, Females: {len(females)}")
        current_app.logger.info(f"Tables: {num_tables}, Rounds: {num_rounds}\n")

        all_compatible_dates = {}
        id_to_user = {}

        # Initialize matches for all attendees
        for attendee in males + females:
            all_compatible_dates[attendee.id] = []
            id_to_user[attendee.id] = attendee

        # Find matches for each attendee
        for attendee in males + females:
            current_app.logger.info(f"\n--- Processing {attendee.first_name} {attendee.last_name} (ID: {attendee.id}) ---")
            current_app.logger.info(f"Gender: {attendee.gender}, Age: {attendee.calculate_age()}")

            all_opposite_gender = females if attendee.gender == Gender.MALE else males
            current_app.logger.info(f"Total potential matches in opposite gender: {len(all_opposite_gender)}")
            previous_date_user_ids = {
                speed_date.female_id if attendee.gender == Gender.MALE else speed_date.male_id
                for speed_date in EventSpeedDate.query.filter(
                    or_(
                        EventSpeedDate.male_id == attendee.id,
                        EventSpeedDate.female_id == attendee.id,
                    )
                ).all()
            }

            compatible_dates = [
                potential_date for potential_date in all_opposite_gender
                if (attendee.church_id is None or potential_date.church_id is None or attendee.church_id != potential_date.church_id)
                    and (abs(attendee.calculate_age() - potential_date.calculate_age()) <= 3)
                    and potential_date.id not in previous_date_user_ids
            ]
            current_app.logger.info(f"\nInitial len of compatible dates (age diff <= 3): {len(compatible_dates)}")

            # If not enough matches, try extended age range
            num_same_gender = (len(females) if attendee.gender == Gender.FEMALE else len(males))
            min_dates_needed = SpeedDateMatcher.min_dates_threshold(num_tables, num_rounds, num_same_gender)
            current_app.logger.info(f"\nMinimum dates needed: {min_dates_needed}")
            current_app.logger.info(f"Current compatible dates: {len(compatible_dates)}")

            if len(compatible_dates) < min_dates_needed:
                current_app.logger.info("\nNot enough matches, trying extended age range (<= 4)")
                compatible_dates = [
                    potential_date for potential_date in all_opposite_gender
                    if (attendee.church_id is None or potential_date.church_id is None or attendee.church_id != potential_date.church_id)
                        and (abs(attendee.calculate_age() - potential_date.calculate_age()) <= 4)
                        and potential_date.id not in previous_date_user_ids
                ]
                current_app.logger.info(f"New number of compatible dates with age <= 4: {len(compatible_dates)}")

            if len(compatible_dates) < min_dates_needed:
                current_app.logger.info("\nStill not enough matches, trying maximum age range (<= 5)")
                compatible_dates = [
                    potential_date for potential_date in all_opposite_gender
                    if (attendee.church_id is None or potential_date.church_id is None or attendee.church_id != potential_date.church_id)
                        and (abs(attendee.calculate_age() - potential_date.calculate_age()) <= 5)
                        and potential_date.id not in previous_date_user_ids
                ]
                current_app.logger.info(f"New number of compatible dates with age <= 5: {len(compatible_dates)}")

            if len(compatible_dates) < min_dates_needed:
                current_app.logger.info("\nStill not enough matches, finding matches at same church")
                compatible_dates = [
                    potential_date for potential_date in all_opposite_gender
                    if (abs(attendee.calculate_age() - potential_date.calculate_age()) <= 5)
                        and potential_date.id not in previous_date_user_ids
                ]
                current_app.logger.info(f"Current compatible dates: {len(compatible_dates)}")

            all_compatible_dates[attendee.id] = compatible_dates
            current_app.logger.info(
                f"\nFinal compatible dates for {attendee.first_name} {attendee.last_name}: {len(compatible_dates)}"
            )

        return (all_compatible_dates, id_to_user)

    @staticmethod
    def min_dates_threshold(num_tables, num_rounds, num_same_gender) -> int:
        if num_same_gender == 0:
            return 0
        max_dates = math.ceil(num_tables * (num_rounds / num_same_gender))
        return math.floor(max_dates)

    @staticmethod
    def finalize_all_rounds(
        all_compatible_dates: Dict[int, List[User]],
        id_to_user: Dict[int, User],
        event_id: int,
        num_tables: int,
        num_rounds: int,
    ) -> List[EventSpeedDate]:
        current_app.logger.info(f"\n\n\n=== Starting schedule generation for event {event_id} ===")
        current_app.logger.info(f"Requested rounds: {num_rounds}, Tables: {num_tables}")
        current_app.logger.info(f"Total attendees: {len(all_compatible_dates)}\n\n\n")

        event_speed_dates: List[EventSpeedDate] = []
        rounds_completed_per_attendee: Dict[int, int] = { # initialize with 0 for each attendee id
            k: 0 for k,_ in all_compatible_dates.items()
        }

        for current_round in range(1, num_rounds + 1):
            current_app.logger.info("\n---\nFilling up all tables for ROUND %d\n---\n\n", current_round)
            current_app.logger.info(f"Tables to fill: {num_tables}")

            # Sort attendees by least number of rounds participated in then by least potential dates
            sorted_attendees = sorted(
                all_compatible_dates,
                key=lambda user_id: (rounds_completed_per_attendee[user_id], len(all_compatible_dates[user_id]),)
            )
            attendees_seated_this_round = set()
            tables_available_this_round = [table_number for table_number in range(1, num_tables + 1)]
            
            for attendee_id in sorted_attendees:
                attendee = id_to_user[attendee_id]
                if attendee_id in attendees_seated_this_round:
                    current_app.logger.info(f"User {attendee_id} ({attendee.first_name} {attendee.last_name}) already seated this round, skipping")
                    continue

                current_app.logger.info(f"\nTrying to seat User {attendee_id} ({attendee.first_name} {attendee.last_name})")

                # sort this attendee's compatible dates by fewest rounds participated in then by age difference
                sorted_compatible_dates = sorted(
                    all_compatible_dates[attendee_id],
                    key=lambda user: (rounds_completed_per_attendee[user.id], abs(user.calculate_age() - attendee.calculate_age()),),
                )

                for compatible_date in sorted_compatible_dates:
                    if compatible_date.id not in attendees_seated_this_round:
                        male_id = attendee_id if attendee.gender == Gender.MALE else compatible_date.id
                        female_id = attendee_id if attendee.gender == Gender.FEMALE else compatible_date.id

                        # set attendee and compatible_date to have a table this round.
                        previous_tables = [
                            esd.table_number for esd in event_speed_dates
                            if esd.round_number == current_round - 1 and (esd.female_id == female_id or esd.male_id == male_id) and esd.table_number in tables_available_this_round
                        ]
                        previous_table = previous_tables[0] if previous_tables else None
                        if previous_table:
                            table_number = previous_table
                            current_app.logger.info(f"Reusing previous table {previous_table}")
                            tables_available_this_round.remove(previous_table)
                        else:
                            table_number = tables_available_this_round.pop(0)
                        SpeedDateMatcher.assign_table(event_speed_dates, event_id, male_id, female_id, table_number, current_round)

                        male_user = id_to_user[male_id]
                        female_user = id_to_user[female_id]
                        current_app.logger.info(
                            f"\nAssigned table {table_number} for round {current_round}:"
                            f"\n  Male: {male_user.first_name} {male_user.last_name} (ID: {male_id})"
                            f"\n  Female: {female_user.first_name} {female_user.last_name} (ID: {female_id})"
                        )

                        # track that both these people are now in the current round
                        attendees_seated_this_round.update([attendee_id, compatible_date.id])
                        rounds_completed_per_attendee[attendee_id] += 1
                        rounds_completed_per_attendee[compatible_date.id] += 1

                        # remove each other from their compatible dates list
                        if compatible_date in all_compatible_dates[attendee_id]:
                            all_compatible_dates[attendee_id].remove(compatible_date)
                        if attendee in all_compatible_dates[compatible_date.id]:
                            all_compatible_dates[compatible_date.id].remove(attendee)

                        current_app.logger.info(f"\nMale {male_id} with Female {female_id} for Round {current_round} at Table {table_number}")
                        current_app.logger.info(f"\n{id_to_user[male_id]}{id_to_user[female_id]}")
                        current_app.logger.info(f"tables now available this round {tables_available_this_round}")
                        current_app.logger.info(f"Rounds per user id:\n {sorted(rounds_completed_per_attendee.items(), key=lambda item: item[1])}\n")

                        break  # this compatible date has a date this round. moving on to next...

                if len(tables_available_this_round) == 0:
                    current_app.logger.info("All tables are filled for ROUND %d\n\n", current_round)
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
        event_speed_date = EventSpeedDate(
            event_id=event_id,
            male_id=male_id,
            female_id=female_id,
            table_number=table_number,
            round_number=round_number,
        )
        event_speed_dates.append(event_speed_date)
