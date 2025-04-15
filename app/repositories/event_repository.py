from app.extensions import db
from app.models import Event

class EventRepository:
    @staticmethod
    def get_events():
        return Event.query
   
    