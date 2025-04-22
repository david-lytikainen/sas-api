from flask import Blueprint, jsonify, request
from app.models.event import Event
from app.models.user import User
from app.models.event_attendee import EventAttendee
from app.models.enums import EventStatus, RegistrationStatus
from app.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_cors import cross_origin
from app.exceptions import UnauthorizedError, MissingFieldsError
from app.services.event_service import EventService
from app.models.role import Role

event_bp = Blueprint("event", __name__)


@event_bp.route("/events", methods=["GET", "OPTIONS"])
def get_events():
    if request.method == "OPTIONS":
        return "", 204

    verify_jwt_in_request()
    user_id = get_jwt_identity()
    return jsonify(EventService.get_events_for_user(user_id))


@event_bp.route("/events/create", methods=["POST"])
@jwt_required()
def create_event():
    current_user_id = get_jwt_identity()
    data = request.get_json()

    try:
        event = EventService.create_event(data, current_user_id)
        return jsonify(event.to_dict()), 201
    except MissingFieldsError as e:
        return (
            jsonify({"error": "Missing required fields", "missing_fields": e.fields}),
            400,
        )
    except UnauthorizedError:
        return jsonify({"error": "Unauthorized"}), 403
    except Exception as e:
        db.session.rollback()
        print(f"Error creating event: {str(e)}")
        return jsonify({"error": "Failed to create event"}), 500


@event_bp.route("/events/<int:event_id>/register", methods=["POST"])
@jwt_required()
def register_for_event(event_id):
    try:
        current_user_id = get_jwt_identity()
        print(
            f"Processing registration for user {current_user_id} for event {event_id}"
        )

        # Get the event
        event = Event.query.get_or_404(event_id)
        print(f"Found event: {event}")

        # Check if already registered
        existing_registration = EventAttendee.query.filter_by(
            event_id=event_id, user_id=current_user_id
        ).first()

        if existing_registration:
            print(f"User {current_user_id} is already registered for event {event_id}")
            return jsonify({"error": "Already registered for this event"}), 400

        if event.status != EventStatus.REGISTRATION_OPEN:
            print(
                f"Event {event_id} is not open for registration. Status: {event.status}"
            )
            return jsonify({"error": "Event is not open for registration"}), 400

        registration = EventAttendee(
            event_id=event_id,
            user_id=current_user_id,
            status=RegistrationStatus.REGISTERED,
        )

        db.session.add(registration)
        db.session.commit()
        print(f"Successfully registered user {current_user_id} for event {event_id}")

        user = User.query.get(current_user_id)
        return jsonify(user.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error registering for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to register for event"}), 500


@event_bp.route("/events/<int:event_id>/register", methods=["DELETE"])
@cross_origin(supports_credentials=True)
@jwt_required()
def cancel_registration(event_id):
    try:
        current_user_id = get_jwt_identity()
        registration = EventAttendee.query.filter_by(
            event_id=event_id, user_id=current_user_id
        ).first_or_404()

        db.session.delete(registration)
        db.session.commit()

        return "", 204
    except Exception as e:
        db.session.rollback()
        print(f"Error cancelling registration for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to cancel registration"}), 500


@event_bp.route("/events/<int:event_id>/start", methods=["POST"])
@cross_origin(supports_credentials=True)
@jwt_required()
def start_event(event_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        event = Event.query.get_or_404(event_id)

        if current_user.role_id not in [Role.ADMIN.value, Role.ORGANIZER.value]:
            return jsonify({"error": "Unauthorized"}), 403

        if (
            current_user.role_id == Role.ORGANIZER.value
            and event.creator_id != current_user_id
        ):
            return jsonify({"error": "Unauthorized"}), 403

        if event.status != EventStatus.PUBLISHED:
            return jsonify({"error": "Event cannot be started"}), 400

        event.status = EventStatus.IN_PROGRESS
        db.session.commit()

        return jsonify({"message": "Event started successfully"})
    except Exception as e:
        db.session.rollback()
        print(f"Error starting event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to start event"}), 500


@event_bp.route("/events/<int:event_id>/registrations", methods=["GET"])
@jwt_required()
def get_event_registrations(event_id):
    try:
        registrations = EventAttendee.query.filter_by(event_id=event_id).all()

        result = [
            {
                "user_id": reg.user_id,
                "status": reg.status.value,
                "registration_date": (
                    reg.registration_date.isoformat() if reg.registration_date else None
                ),
                "check_in_date": (
                    reg.check_in_date.isoformat() if reg.check_in_date else None
                ),
            }
            for reg in registrations
        ]

        return jsonify(result), 200

    except Exception as e:
        print(f"Error getting registrations for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to get registrations"}), 500
