from enum import Enum

class EventStatus(Enum):
    OPEN = 'open'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

class UserRole(Enum):
    ADMIN = 1
    ORGANIZER = 2
    ATTENDEE = 3

class Gender(Enum):
    MALE = 'MALE'
    FEMALE = 'FEMALE'

class RegistrationStatus(Enum):
    REGISTERED = 'registered'
    CHECKED_IN = 'checked_in'
    CANCELLED = 'cancelled'
    