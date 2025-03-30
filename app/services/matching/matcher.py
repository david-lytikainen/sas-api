from typing import List, Dict
from app.models.user import User
from app.models.enums import Gender
from app.models.event_speed_date import EventSpeedDate
from app.extensions import db

class SpeedDateMatcher:
    def __init__(self, event_id: int):
        self.event_id = event_id
        self.male_attendees = []
        self.female_attendees = []

    def find_all_possible_matches(self, males: List[User], females: List[User], 
                                min_dates: int,
                                initial_age_range: int = 3,
                                extended_age_range: int = 5) -> Dict[int, List[User]]:
        """
        Find all possible matches for each participant based on age compatibility.
        Ensures each person has at least min_dates potential matches.
        
        Args:
            males: List of male participants
            females: List of female participants
            min_dates: Minimum number of dates each person should have
            initial_age_range: Initial maximum age difference allowed (default ±3 years)
            extended_age_range: Extended age range if initial is too restrictive (default ±5 years)
            
        Returns:
            Dictionary mapping each participant's ID to a list of compatible Users
        """
        all_matches = {}
        
        # Initialize matches for all participants
        for participant in males + females:
            all_matches[participant.id] = []
        
        # Find matches for each participant
        for participant in males + females:
            # Determine which group to match with
            potential_matches = females if participant.gender == Gender.MALE else males
            
            # Try with initial age range
            compatible_matches = [
                match for match in potential_matches
                if abs(participant.age - match.age) <= initial_age_range
            ]
            
            # If not enough matches, try extended age range
            if len(compatible_matches) < min_dates:
                compatible_matches = [
                    match for match in potential_matches
                    if abs(participant.age - match.age) <= extended_age_range
                ]
            
            # Sort matches by age difference
            compatible_matches.sort(key=lambda x: abs(x.age - participant.age))
            
            # Store matches
            all_matches[participant.id] = compatible_matches
        
        return all_matches

    def create_date_schedule(self, males: List[User], females: List[User], 
                           min_dates: int, max_dates: int, num_tables: int) -> List[EventSpeedDate]:
        """
        Create a schedule of dates ensuring each person gets between min_dates and max_dates.
        Prioritizes participants with fewer potential matches.
        
        Args:
            males: List of male participants
            females: List of female participants
            min_dates: Minimum number of dates each person should have
            max_dates: Maximum number of dates each person can have
            num_tables: Number of tables available for each round
            
        Returns:
            List of created EventSpeedDate records
        """
        # Get all possible matches
        all_matches = self.find_all_possible_matches(males, females, min_dates)
        
        # Initialize schedule and tracking
        speed_dates = []
        dates_per_participant = {p.id: 0 for p in males + females}  # Track dates for everyone
        used_pairs = set()  # Track which pairs have already met
        
        # Sort participants by number of potential matches (ascending)
        participants = males + females
        participants.sort(key=lambda p: len(all_matches[p.id]))
        
        # Create schedule round by round
        current_round = 1
        while any(dates < min_dates for dates in dates_per_participant.values()):
            tables_used = 0  # Track number of tables used in current round
            
            # Try to schedule dates for each participant
            for participant in participants:
                # Skip if we've used all tables in this round
                if tables_used >= num_tables:
                    break
                    
                # Skip if participant has reached max dates
                if dates_per_participant[participant.id] >= max_dates:
                    continue
                    
                # Get available matches for this participant
                available_matches = [
                    match for match in all_matches[participant.id]
                    if dates_per_participant[match.id] < max_dates
                    and (participant.id, match.id) not in used_pairs
                ]
                
                if available_matches:
                    # Take the first available match (they're already sorted by age difference)
                    match = available_matches[0]
                    
                    # Create EventSpeedDate record
                    speed_date = EventSpeedDate(
                        event_id=self.event_id,
                        male_id=participant.id if participant.gender == Gender.MALE else match.id,
                        female_id=match.id if participant.gender == Gender.MALE else participant.id,
                        table_number=tables_used + 1,  # Tables start at 1
                        round_number=current_round
                    )
                    speed_dates.append(speed_date)
                    
                    # Update tracking
                    dates_per_participant[participant.id] += 1
                    dates_per_participant[match.id] += 1
                    used_pairs.add((participant.id, match.id))
                    tables_used += 1
            
            current_round += 1
            
            # Break if we've gone too many rounds without progress
            if current_round > (max_dates * 2):  # Safety break
                break
        
        # Save all speed dates to the database
        db.session.add_all(speed_dates)
        db.session.commit()
        
        return speed_dates

    
        