from app.models import User
from app.models.enums import Gender
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from flask import current_app
from app.repositories import UserRepository
from datetime import timedelta, datetime
import logging
from app.models.church import Church
from app.utils.email import send_password_reset_email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserService:
    @staticmethod
    def sign_up(user_data):
        try:
            # Check if user exists
            existing_user = UserRepository.find_by_email(user_data["email"])
            if existing_user:
                logger.warning(
                    f"Signup attempt with existing email: {user_data['email']}"
                )
                raise ValueError("User already exists")

            # Hash password
            hashed_password = generate_password_hash(user_data["password"])

            # Handle gender - convert to uppercase and validate against enum
            gender_str = user_data["gender"].upper()
            try:
                gender = Gender[gender_str]
            except KeyError:
                logger.warning(f"Invalid gender value: {gender_str}")
                raise ValueError("Invalid gender value. Must be either MALE or FEMALE")

            # --- Church name to ID mapping ---
            church_id = None
            church_name = user_data.get("current_church")
            if church_name and church_name != "Other":
                church = Church.query.filter_by(name=church_name).first()
                if not church:
                    # Create new church if not found
                    church = Church(name=church_name)
                    from app.extensions import db

                    db.session.add(church)
                    db.session.commit()
                church_id = church.id

            # Create user object
            user = User(
                role_id=user_data["role_id"],
                email=user_data["email"],
                password=hashed_password,
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                phone=user_data["phone"],
                gender=gender,
                birthday=datetime.strptime(user_data["birthday"], "%Y-%m-%d").date(),
                church_id=church_id,
                denomination_id=user_data.get("denomination_id"),
            )

            # Save user to database
            created_user = UserRepository.sign_up(user)
            if not created_user:
                raise ValueError("Failed to create user")

            # Generate token
            access_token = create_access_token(
                identity=created_user.id, expires_delta=timedelta(days=1)
            )

            logger.info(f"User created successfully: {created_user.email}")

            return {"token": access_token, "user": created_user.to_dict()}
        except ValueError as e:
            logger.error(f"Signup error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during signup: {str(e)}")
            raise ValueError("An error occurred during signup")

    @staticmethod
    def sign_in(email, password):
        try:
            # Find user
            user = UserRepository.find_by_email(email)
            if not user:
                logger.warning(f"Login attempt with non-existent email: {email}")
                raise ValueError("Invalid email")

            # Verify password
            if not check_password_hash(user.password, password):
                logger.warning(f"Failed login attempt for user: {email}")
                raise ValueError("Invalid password")

            # Generate token
            access_token = create_access_token(
                identity=str(user.id), expires_delta=timedelta(days=1)
            )

            logger.info(f"User logged in successfully: {email}")

            return {"token": access_token, "user": user.to_dict()}
        except ValueError as e:
            logger.error(f"Login error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during login: {str(e)}")
            raise ValueError("An error occurred during login")

    @staticmethod
    def forgot_password(email):
        try:
            user = UserRepository.find_by_email(email)
            response = {"message": "If an account with that email exists, a password reset link has been sent."}

            if user:
                send_password_reset_email(user)
                logger.info(f"Password reset email sent to {email}")
                if current_app.testing:
                    response['reset_token'] = user.reset_token
            else:
                logger.warning(
                    f"Password reset attempted for non-existent email: {email}"
                )
            
            return response
        except Exception as e:
            logger.error(f"Error in forgot_password service: {str(e)}")
            # Even in case of an unexpected error, return a generic message
            return {"message": "If an account with that email exists, a password reset link has been sent."}

    @staticmethod
    def reset_password(token, new_password):
        try:
            user = User.verify_reset_token(token)
            if not user:
                logger.warning("Invalid or expired password reset token received.")
                raise ValueError("Invalid or expired token")

            # Hash new password
            hashed_password = generate_password_hash(new_password)
            user.password = hashed_password
            user.reset_token = None
            user.reset_token_expiration = None
            
            from app.extensions import db
            db.session.commit()
            
            logger.info(f"Password reset successfully for user: {user.email}")
            return {"message": "Your password has been reset successfully."}
        except ValueError as e:
            logger.error(f"Password reset error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during password reset: {str(e)}")
            raise ValueError("An error occurred during password reset")
