from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User
from app.models.enums import Gender
from app.models.church import Church
from app.extensions import db
from app.utils.email import send_password_reset_email
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from flask import current_app
from datetime import timedelta, datetime
import logging

user_bp = Blueprint("user", __name__)
logger = logging.getLogger(__name__)


def find_user_by_email(email):
    return User.query.filter_by(email=email).first()


def sign_up_user(user_data):
    existing_user = find_user_by_email(user_data["email"])
    if existing_user:
        raise ValueError("User already exists")

    gender_str = user_data["gender"].upper()
    try:
        gender = Gender[gender_str]
    except KeyError:
        raise ValueError("Invalid gender value. Must be either MALE or FEMALE")

    church_id = None
    church_name = user_data.get("current_church")
    if church_name and church_name != "Other":
        church = Church.query.filter_by(name=church_name).first()
        if not church:
            church = Church(name=church_name)
            db.session.add(church)
            db.session.commit()
        church_id = church.id

    user = User(
        role_id=user_data["role_id"],
        email=user_data["email"],
        password=generate_password_hash(user_data["password"]),
        first_name=user_data["first_name"],
        last_name=user_data["last_name"],
        phone=user_data["phone"],
        gender=gender,
        birthday=datetime.strptime(user_data["birthday"], "%Y-%m-%d").date(),
        church_id=church_id,
        denomination_id=user_data.get("denomination_id"),
    )

    db.session.add(user)
    db.session.commit()
    access_token = create_access_token(identity=user.id, expires_delta=timedelta(days=1))
    return {"token": access_token, "user": user.to_dict()}


def sign_in_user(email, password):
    user = find_user_by_email(email)
    if not user:
        raise ValueError("Invalid email")
    if not check_password_hash(user.password, password):
        raise ValueError("Invalid password")

    access_token = create_access_token(identity=str(user.id), expires_delta=timedelta(days=1))
    return {"token": access_token, "user": user.to_dict()}


def send_forgot_password_email(email):
    user = find_user_by_email(email)
    response = {"message": "Password reset link has been sent."}

    if user:
        send_password_reset_email(user)
        if current_app.testing:
            response["reset_token"] = user.reset_token
    return response


def reset_user_password(token, new_password):
    user = User.verify_reset_token(token)
    if not user:
        raise ValueError("Invalid or expired token")

    user.password = generate_password_hash(new_password)
    user.reset_token = None
    user.reset_token_expiration = None
    db.session.commit()
    return {"message": "Your password has been reset successfully."}


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
            return (jsonify({"error": "Missing required fields", "missing_fields": missing_fields,}),400,)

        result = sign_up_user(user_data)
        return make_response(jsonify(result), 201)
    except ValueError as e:
        if str(e) == "User already exists":
            return (jsonify({"error": "An account already exists for this email. Please go to Sign In and use Forgot Password if needed."}),409,)
        return jsonify({"error": str(e)}), 400
    except Exception:
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

        result = sign_in_user(user_data["email"], user_data["password"])
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

        result = send_forgot_password_email(data["email"])
        return jsonify(result), 200
    except Exception:
        # Generic error to avoid leaking information
        return (
            jsonify({"error": "An error occurred while processing your request."}),
            500,
        )


@user_bp.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    try:
        data = request.get_json()
        if not data or "password" not in data:
            return jsonify({"error": "Password is required"}), 400

        result = reset_user_password(token, data["password"])
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "An unexpected error occurred"}), 500


@user_bp.route("/churches", methods=["GET"])
def get_churches():
    try:
        churches = Church.query.order_by(Church.name.asc()).all()
        return jsonify([church.name for church in churches]), 200
    except Exception:
        return jsonify({"error": "Failed to fetch churches"}), 500
