from flask import Blueprint, request, jsonify, make_response
from app.services import UserService
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User

user_bp = Blueprint("user", __name__)


@user_bp.route("/signup", methods=["POST"])
def sign_up():
    try:
        user_data = request.get_json()
        print(user_data)
        if not user_data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = [
            "email",
            "password",
            "role_id",
            "first_name",
            "last_name",
            "phone",
            "gender",
            "birthday",
        ]
        missing_fields = [field for field in required_fields if field not in user_data]

        if missing_fields:
            return (
                jsonify(
                    {
                        "error": "Missing required fields",
                        "missing_fields": missing_fields,
                    }
                ),
                400,
            )

        result = UserService.sign_up(user_data)
        return make_response(jsonify(result), 201)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred"}), 500


@user_bp.route("/signin", methods=["POST", "OPTIONS"])
def sign_in():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    try:
        user_data = request.get_json()
        if not user_data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ["email", "password"]
        missing_fields = [field for field in required_fields if field not in user_data]

        if missing_fields:
            return (
                jsonify(
                    {
                        "error": "Missing required fields",
                        "missing_fields": missing_fields,
                    }
                ),
                400,
            )

        result = UserService.sign_in(user_data["email"], user_data["password"])
        response = make_response(jsonify(result), 200)
        return response
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@user_bp.route("/validate-token", methods=["GET"])
@jwt_required()
def validate_token():
    try:
        # Get the authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "No authorization header"}), 401

        # Check if the token is properly formatted
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Invalid token format"}), 401

        current_user_id = get_jwt_identity()
        if not current_user_id:
            return jsonify({"error": "No user ID found in token"}), 401

        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"valid": True, "user": current_user.to_dict()})
    except Exception as e:
        print(f"Token validation error: {str(e)}")
        return jsonify({"error": "Invalid or expired token"}), 401


@user_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    try:
        data = request.get_json()
        if not data or "email" not in data:
            return jsonify({"error": "Email is required"}), 400

        result = UserService.forgot_password(data["email"])
        return jsonify(result), 200
    except Exception as e:
        # Generic error to avoid leaking information
        return jsonify({"error": "An error occurred while processing your request."}), 500


@user_bp.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    try:
        data = request.get_json()
        if not data or "password" not in data:
            return jsonify({"error": "Password is required"}), 400

        result = UserService.reset_password(token, data["password"])
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred"}), 500
