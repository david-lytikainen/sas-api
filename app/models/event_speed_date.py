from app.extensions import db


class EventSpeedDate(db.Model):
    __tablename__ = "events_speed_dates"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    male_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    female_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
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

    def record_interest(self, user_id: int, interested: bool) -> None:
        """
        Records the interest of a participating user for this speed date.

        The attendee (user) indicates their interest in the other participant
        of this specific speed date instance.

        Args:
            user_id: The ID of the user (attendee) expressing interest.
                     This user must be either the male_id or female_id for this speed date.
            interested: A boolean indicating whether the user is interested
                        (True for 'yes', False for 'no').

        Raises:
            ValueError: If the provided user_id is not one of the participants
                        (male_id or female_id) in this speed date.
        """
        if self.male_id == user_id:
            self.male_interested = interested
        elif self.female_id == user_id:
            self.female_interested = interested
        else:
            raise ValueError(
                f"User with ID {user_id} is not a participant in this speed date "
                f"(Male ID: {self.male_id}, Female ID: {self.female_id})."
            )
        # Note: This method modifies the instance in memory.
        # The caller (e.g., a service layer or API endpoint) is responsible
        # for persisting changes to the database, typically by committing
        # the SQLAlchemy session (e.g., db.session.commit()).
