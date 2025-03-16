from app.models import User
from werkzeug.security import generate_password_hash
from app.repositories import UserRepository

class UserService:
    @staticmethod
    def create_user(user_data):
        if UserRepository.find_by_email(user_data['email']):
            raise Exception('User already exists')
        
        hashed_password = generate_password_hash(user_data['password']).decode('utf-8')

        user = User(
            role_id=user_data['role_id'],
            email=user_data['email'],
            password=hashed_password,
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            phone=user_data['phone'],
            gender=user_data['gender'],
            age=user_data['age'],
            church_id=user_data.get('church_id'),
            denomination_id=user_data.get('denomination_id')
        )

        return UserRepository.create_user(user)
