from app.extensions import db

class EventSpeedDate(db.Model):
    __tablename__ = 'events_speed_dates'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    male_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    female_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    male_interested = db.Column(db.Boolean, nullable=True)
    female_interested = db.Column(db.Boolean, nullable=True)
    table_number = db.Column(db.Integer, nullable=False)
    round_number = db.Column(db.Integer, nullable=False)
    
    def __repr__(self):
        return (
            f"EventSpeedDate("
            f"id={self.id}, "
            f"event_id={self.event_id}, "
            f"male_id='{self.male_id}', "
            f"female_id='{self.female_id}', "
            f"table_number={self.table_number}, "
            f"round_number={self.round_number}"
            f")\n"
        )