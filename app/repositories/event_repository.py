from app.extensions import db
from app.models import Event


class EventRepository:
    @staticmethod
    def get_events():
        return Event.query

    @staticmethod
    def get_event(event_id: int) -> Event:
        return Event.query.filter_by(id=event_id).first()

    @staticmethod
    def create_event(attrs):
        event = Event(**attrs)
        db.session.add(event)
        db.session.commit()
        return event

    @staticmethod
    def update_event(event: Event, attrs: dict):
        for key, value in attrs.items():
            if hasattr(event, key):
                setattr(event, key, value)
        db.session.commit()
        return event

    @staticmethod
    def delete_event(event: Event):
        db.session.delete(event)
        db.session.commit()
