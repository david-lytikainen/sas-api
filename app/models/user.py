from app.extensions import db
from datetime import date, datetime, timedelta, timezone
from .enums import Gender
import secrets
from flask import current_app


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    reset_token = db.Column(db.String(255), unique=True, nullable=True)
    reset_token_expiration = db.Column(db.TIMESTAMP(timezone=True), nullable=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.Enum(Gender), nullable=False)
    birthday = db.Column(db.Date, nullable=False)
    church_id = db.Column(db.Integer, db.ForeignKey("churches.id"), nullable=True)
    denomination_id = db.Column(
        db.Integer, db.ForeignKey("denominations.id"), nullable=True
    )
    updated_at = db.Column(
        db.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now()
    )

    def calculate_age(self):
        today = date.today()
        return (
            today.year
            - self.birthday.year
            - ((today.month, today.day) < (self.birthday.month, self.birthday.day))
        )

    def get_reset_token(self, expires_sec=1800):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiration = datetime.now(timezone.utc) + timedelta(
            seconds=expires_sec
        )
        db.session.commit()
        return self.reset_token

    @staticmethod
    def verify_reset_token(token):
        user = User.query.filter_by(reset_token=token).first()
        if (
            user
            and user.reset_token_expiration
            and user.reset_token_expiration > datetime.now(timezone.utc)
        ):
            return user
        return None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, User):
            return self.id == other.id
        return False

    def to_dict(self):
        return {
            "id": self.id,
            "role_id": self.role_id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "gender": self.gender.value if self.gender else None,
            "birthday": self.birthday if self.birthday else None,
            "age": self.calculate_age(),
            "church_id": self.church_id,
            "denomination_id": self.denomination_id,
        }

    def __repr__(self):
        return (
            f"User("
            f"id={self.id}, "
            f"age={self.calculate_age()}, "
            f"first_name='{self.first_name}', "
            f"last_name='{self.last_name}', "
            f"gender={self.gender}"
            f")\n"
        )
