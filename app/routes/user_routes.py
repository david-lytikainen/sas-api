from flask import Blueprint, request, jsonify
from app.services import UserService

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/signup', methods=['POST'])
def sign_up():
    user_data = request.get_json()
    if not user_data:
        return jsonify({"error": "no data provided"}), 400
    
    required_fields = ['email', 'password', 'role_id', 'first_name', 
                       'last_name', 'phone', 'gender', 'age']
    if not all(field in user_data for field in required_fields):
        return jsonify({"error": "missing required fields"}), 400
    
    try:
        UserService.sign_up(user_data)
        return jsonify({"message": "user created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
@user_bp.route('/signin', methods=['POST'])
def sign_in():
    user_data = request.get_json()
    if not user_data:
        return jsonify({"error": "no data provided"}), 400
    
    required_fields = ['email', 'password']
    if not all(field in user_data for field in required_fields):
        return jsonify({"error": "missing required fields"}), 400
    
    try:
        result = UserService.sign_in(user_data['email'], user_data['password'])
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 401
        
    