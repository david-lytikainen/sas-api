from app import db

class EventDate(db.Model):
    __tablename__ = 'events_dates'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    male_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    female_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    table_number = db.Column(db.Integer, nullable=False)
    round_number = db.Column(db.Integer, nullable=False)
    