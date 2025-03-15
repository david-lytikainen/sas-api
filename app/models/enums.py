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
    