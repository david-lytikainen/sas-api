from typing import List, Dict
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
                                  initial_age_range: int = 3, 
                                  extended_age_range: int = 4) -> Dict[int, List[User]]:
        """
        Find all potential matches for each attendee.
        +-3 years age difference (+-4 years if they don't have the threshold amount of potential dates)
        Each attendee's list of potential dates is sorted based on closeness of age to the attendee
        """
        all_dates = {}
        
        # Initialize matches for all attendees
        for attendee in males + females:
            all_dates[attendee.id] = []
        
        # Find matches for each attendee
        for attendee in males + females:
            potential_dates = females if attendee.gender == Gender.MALE else males
            
            # Try with initial age range
            compatible_dates = [
                match for match in potential_dates
                if abs(attendee.calculate_age() - match.calculate_age()) <= initial_age_range
            ]
            
            # If not enough matches, try extended age range
            if len(compatible_dates) < SpeedDateMatcher.min_dates_threshold(len(potential_dates)):
                compatible_dates = [
                    match for match in potential_dates
                    if abs(attendee.age - match.age) <= extended_age_range
                ]
            
            # Sort matches by age difference
            compatible_dates.sort(key=lambda x: abs(x.calculate_age() - attendee.calculate_age()))
            all_dates[attendee.id] = compatible_dates
        
        return all_dates
    
    @staticmethod
    def min_dates_threshold(num_potential_matches: int) -> int:
        # The threshold is num of opposite gender * .25
        return math.ceil(num_potential_matches * .25)

    



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
            matches = SpeedDateMatcher.find_all_potential_dates(males, females)

            print([attendee.calculate_age() for attendee in attendees])
            print("\n\n\n\n")
            print(matches)

if __name__ == '__main__':
    SpeedDateMatcher.test_find_all()