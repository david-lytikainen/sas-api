from app.extensions import db
from typing import List
from app.models import EventSpeedDate


class EventSpeedDateRepository:
    @staticmethod
    def save_all(event_speed_dates: List[EventSpeedDate]):
        db.session.bulk_save_objects(event_speed_dates)
        db.session.commit()
