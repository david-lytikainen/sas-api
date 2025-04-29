from app.extensions import db
from app.models import Event


class EventRepository:
    @staticmethod
    def get_events():
        return Event.query

    @staticmethod
    def get_event(event_id: int):
        return Event.query.filter_by(id=event_id).first()
   
    @staticmethod
    def create_event(attrs):
        event = Event(**attrs)
        db.session.add(event)
        db.session.commit()
        return event
