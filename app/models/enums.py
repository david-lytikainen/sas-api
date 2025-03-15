from enum import Enum

class EventStatus(Enum):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

class Gender(Enum):
    MALE = 'male'
    FEMALE = 'female'

class RegistrationStatus(Enum):
    REGISTERED = 'registered'
    CHECKED_IN = 'checked_in'
    CANCELLED = 'cancelled'
    