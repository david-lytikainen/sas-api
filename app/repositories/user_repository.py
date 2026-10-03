from app.models import User


class UserRepository:
    @staticmethod
    def find_by_id(user_id: int) -> User:
        return User.query.filter_by(id=user_id).first()
