from typing import List, Dict, Tuple
from app.models.user import User
from app.models.enums import Gender
from app.models.event_speed_date import EventSpeedDate
from app.services.event_attendee_service import EventAttendeeService
import math
from app.extensions import db

class SpeedDateMatcher:
    @staticmethod
    def find_all_potential_dates(males: List[User], 
                                 females: List[User], 
                                 num_tables: int,
                                 num_rounds: int,
                                 initial_age_difference: int = 3, 
                                 extended_age_difference: int = 4) -> Tuple[Dict[int, List[User]], Dict[int, User]]:
        """
        Find all potential matches for each attendee.
        +-3 years age difference (+-4 years if they don't have the threshold amount of potential dates)
        Each attendee's list of potential dates is sorted based on closeness of age to the attendee
        """
        all_compatible_dates = {}
        id_to_user = {}
        
        # Initialize matches for all attendees
        for attendee in males + females:
            all_compatible_dates[attendee.id] = []
            id_to_user[attendee.id] = attendee
        
        # Find matches for each attendee
        for attendee in males + females:
            all_opposite_gender = females if attendee.gender == Gender.MALE else males
            
            # Try with initial age range
            compatible_dates = [
                match for match in all_opposite_gender
                if abs(attendee.calculate_age() - match.calculate_age()) <= initial_age_difference
            ]
            
            # If not enough matches, try extended age range
            num_same_gender = len(females) if attendee.gender == Gender.FEMALE else len(males)
            if len(compatible_dates) < SpeedDateMatcher.min_dates_threshold(num_tables, num_rounds, num_same_gender):
                compatible_dates = [
                    match for match in all_opposite_gender
                    if abs(attendee.calculate_age() - match.calculate_age()) <= extended_age_difference
                ]
            
            all_compatible_dates[attendee.id] = compatible_dates
        
        return (all_compatible_dates, id_to_user)
    
    @staticmethod
    def min_dates_threshold(num_tables, num_rounds, num_same_gender) -> int:
        """
        Threshold that determines whether to extend the age range
        first, calculate the max number of dates that person can have
        then, take the floor of max_dates * .5
        """
        max_dates = math.ceil(num_tables * (num_rounds / num_same_gender))
        return math.floor(max_dates * .5)

    @staticmethod
    def finalize_all_rounds(all_compatible_dates: Dict[int, List[User]], 
                            id_to_user: Dict[int, User], 
                            event_id: int,
                            num_tables: int, 
                            num_rounds: int):
        # holds every speed date with each user id, round number, and table number
        event_speed_dates: List[EventSpeedDate] = []

        # tracks how many rounds each attendee has participated in
        rounds_completed_per_attendee: Dict[int, int] = {k:0 for k,_ in all_compatible_dates.items()}
        print(rounds_completed_per_attendee)

        for current_round in range(1, num_rounds+1):
            # Sort attendees by number of rounds participated in then by most potential dates
            sorted_attendees = sorted(
                all_compatible_dates,
                key=lambda user_id: (rounds_completed_per_attendee[user_id], -len(all_compatible_dates[user_id]))
            )
            attendees_seated_this_round = set()

            table_number = 1
            for attendee_id in sorted_attendees:
                attendee = id_to_user[attendee_id]
                if attendee_id in attendees_seated_this_round:
                    continue

                # sort this attendee's compatible dates by fewest rounds participated in then by age difference
                sorted_compatible_dates = sorted(
                    all_compatible_dates[attendee_id],
                    key=lambda user: (rounds_completed_per_attendee[user.id], abs(user.calculate_age() - attendee.calculate_age()))
                )
                
                for compatible_date in sorted_compatible_dates:
                    if compatible_date.id not in attendees_seated_this_round:
                        male_id   = attendee_id if attendee.gender == Gender.MALE else compatible_date.id
                        female_id = attendee_id if attendee.gender == Gender.MALE else compatible_date.id

                        # set attendee and compatible_date to have a table this round.
                        SpeedDateMatcher.assign_table(event_speed_dates, event_id, male_id, female_id, table_number, current_round)
                        table_number += 1

                        # track that both these people are now in the current round
                        rounds_completed_per_attendee[attendee_id] += 1
                        rounds_completed_per_attendee[compatible_date.id] += 1
                        attendees_seated_this_round.update([attendee_id, compatible_date.id])

                        # remove each other from their compatible dates list
                        all_compatible_dates[attendee_id].remove(compatible_date)
                        if attendee in all_compatible_dates[compatible_date.id]:
                            all_compatible_dates[compatible_date.id].remove(attendee)

                if table_number > num_tables:
                    break # all tables are filled this round

        # TODO later: try to keep people at same table

    @staticmethod
    def assign_table(event_speed_dates: List[EventSpeedDate], event_id: int, male_id: int, female_id: int, 
                     table_number: int, round_number: int):
        """
        In place update event_speed_dates, adding the new speed date to it with table_number and round_number
        """
        event_speed_date = EventSpeedDate(
            event_id=event_id,
            male_id=male_id,
            female_id=female_id,
            table_number=table_number,
            round_number=round_number
        )
        event_speed_dates.append(event_speed_date)

    @staticmethod
    def test_find_all():
        from app import create_app
        
        app = create_app()  # Or however you initialize your Flask app
        
        with app.app_context():
            attendees = EventAttendeeService.get_checked_in_attendees(3)
            attendees.sort(key= lambda a: a.calculate_age())
            
            males = [user for user in attendees if user.gender == Gender.MALE]
            females = [user for user in attendees if user.gender == Gender.FEMALE]
            
            print(f"Found {len(males)} males and {len(females)} females")
            all_compatible_dates = SpeedDateMatcher.find_all_potential_dates(males, females, 10, 10)

            print([attendee.calculate_age() for attendee in attendees])
            print("\n\n\n\n")

            all_attendees_ids = sorted(all_compatible_dates, key=lambda pid: len(all_compatible_dates[pid]), reverse=True)
            all_attendees_num_potential = [len(all_compatible_dates[id]) for id in all_attendees_ids]
            print(all_attendees_ids)
            print(all_attendees_num_potential)
            print(all_compatible_dates[64])

if __name__ == '__main__':
    SpeedDateMatcher.test_find_all()