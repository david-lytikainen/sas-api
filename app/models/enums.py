from enum import Enum

class EventStatus(Enum):
    DRAFT = 'DRAFT'
    SCHEDULED = 'SCHEDULED'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'

class Gender(Enum):
    MALE = 'MALE'
    FEMALE = 'FEMALE'
    NOT_SPECIFIED = 'NOT_SPECIFIED'

class RegistrationStatus(Enum):
    REGISTERED = 'registered'
    CHECKED_IN = 'checked_in'
    CANCELLED = 'cancelled'
    