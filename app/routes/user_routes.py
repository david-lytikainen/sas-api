from flask import Blueprint, request, jsonify
from app.services import UserService

user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/signup', methods=['POST'])
def signup():
    user_data = request.get_json()
    if not user_data:
        return jsonify({"error": "no data provided"}), 400
    
    required_fields = ['email', 'password', 'role_id', 'first_name', 
                       'last_name', 'phone', 'gender', 'age']
    
    if not all(field in user_data for field in required_fields):
        return jsonify({"error": "missing required fields"}), 400
    
    try:
        UserService.create_user(user_data)
        return jsonify({"message": "user created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    