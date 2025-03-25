from app.models import User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from app.repositories import UserRepository

class UserService:
    @staticmethod
    def sign_up(user_data):
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
    
    @staticmethod
    def sign_in(email, password):
        user = UserRepository.find_by_email(email)
        if not user or not check_password_hash(user.password, password):
            raise Exception('Invalid email or password')
        
        access_token = create_access_token(identity=user.id)
        return {
            'access_token': access_token,
            user: {
                'id': user.id,
                'email': user.email,
                'role_id': user.role_id,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        }
            
