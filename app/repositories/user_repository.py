from app.extensions import db
from app.models import User

class UserRepository:
    @staticmethod
    def sign_up(user):
        db.session.add(user)
        db.session.commit()
        return user
   
    @staticmethod
    def find_by_email(email):
        return User.query.filter_by(email=email).first()
    