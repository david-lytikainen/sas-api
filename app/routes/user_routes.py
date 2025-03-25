from flask import Blueprint, request, jsonify, make_response
from app.services import UserService
from werkzeug.exceptions import BadRequest
from flask_cors import cross_origin

user_bp = Blueprint('user', __name__)

@user_bp.route('/signup', methods=['POST'])
@cross_origin(supports_credentials=True)
def sign_up():
    try:
        user_data = request.get_json()
        if not user_data:
            return jsonify({"error": "No data provided"}), 400
        
        required_fields = ['email', 'password', 'role_id', 'first_name', 
                        'last_name', 'phone', 'gender', 'age']
        missing_fields = [field for field in required_fields if field not in user_data]
        
        if missing_fields:
            return jsonify({
                "error": "Missing required fields",
                "missing_fields": missing_fields
            }), 400
        
        result = UserService.sign_up(user_data)
        response = make_response(jsonify(result), 201)
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred"}), 500
    
@user_bp.route('/signin', methods=['POST', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def sign_in():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

    try:
        user_data = request.get_json()
        if not user_data:
            return jsonify({"error": "No data provided"}), 400
        
        required_fields = ['email', 'password']
        missing_fields = [field for field in required_fields if field not in user_data]
        
        if missing_fields:
            return jsonify({
                "error": "Missing required fields",
                "missing_fields": missing_fields
            }), 400
        
        result = UserService.sign_in(user_data['email'], user_data['password'])
        response = make_response(jsonify(result), 200)
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500
        
    