from enum import Enum

class EventStatus(Enum):
    REGISTRATION_OPEN = 'Registration Open'
    IN_PROGRESS = 'In Progress'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'

class Gender(Enum):
    MALE = 'Male'
    FEMALE = 'Female'

class RegistrationStatus(Enum):
    REGISTERED = 'Registered'
    CHECKED_IN = 'Checked In'
    CANCELLED = 'Cancelled'
    