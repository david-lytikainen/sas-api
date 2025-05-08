from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.enums import UserRole
from app.extensions import db
from app.exceptions import UnauthorizedError

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/check", methods=["GET"])
@jwt_required()
def check_admin():
    """Check if current user is an admin"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user or user.role_id != UserRole.ADMIN.value:
        return jsonify({"is_admin": False}), 403

    return jsonify({"is_admin": True})


@admin_bp.route("/admin/users", methods=["GET"])
@jwt_required()
def get_all_users():
    """Get all users (admin only)"""
    try:
        # Check admin permissions
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)

        if not user or user.role_id != UserRole.ADMIN.value:
            raise UnauthorizedError("Admin privileges required")

        # Get all users
        users = User.query.all()
        users_data = [user.to_dict(exclude=["password"]) for user in users]

        return jsonify(users_data)

    except UnauthorizedError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to retrieve users: {str(e)}"}), 500


@admin_bp.route("/admin/users/<int:user_id>/role", methods=["PUT"])
@jwt_required()
def update_user_role(user_id):
    """Update a user's role (admin only)"""
    try:
        # Check admin permissions
        current_user_id = get_jwt_identity()
        admin = User.query.get(current_user_id)

        if not admin or admin.role_id != UserRole.ADMIN.value:
            raise UnauthorizedError("Admin privileges required")

        # Get request data
        data = request.get_json()
        new_role_id = data.get("role_id")

        if new_role_id is None:
            return jsonify({"error": "Role ID is required"}), 400

        # Update user
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        user.role_id = new_role_id
        db.session.commit()

        return jsonify({"message": "User role updated successfully"})

    except UnauthorizedError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update user role: {str(e)}"}), 500
