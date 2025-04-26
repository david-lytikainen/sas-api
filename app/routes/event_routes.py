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
import random

event_bp = Blueprint("event", __name__)


@event_bp.route("/events", methods=["GET", "OPTIONS"])
def get_events():
    if request.method == "OPTIONS":
        return "", 204

    verify_jwt_in_request()
    user_id = get_jwt_identity()
    
    # Get all events
    events_data = EventService.get_events_for_user(user_id)
    
    # Get user's registrations
    user_registrations = EventAttendee.query.filter_by(user_id=user_id).all()
    registrations_data = [{"event_id": reg.event_id, "status": reg.status.value} for reg in user_registrations]
    
    # Return both events and registrations
    return jsonify({
        "events": events_data,
        "registrations": registrations_data
    })


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
    current_user_id = get_jwt_identity()
    response = EventService.register_for_event(event_id, current_user_id)
    return jsonify(response)

@event_bp.route('/events/<int:event_id>/cancel-registration', methods=['POST', 'OPTIONS'])
def cancel_registration(event_id):
    if request.method == 'OPTIONS':
        return '', 204
        
    verify_jwt_in_request() 
    user_id = get_jwt_identity()
    EventService.cancel_registration(event_id, user_id)
    return jsonify({'message': 'Registration cancelled successfully'}), 200


@event_bp.route("/events/<int:event_id>/start", methods=["POST"])
@cross_origin(supports_credentials=True)
@jwt_required()
def start_event(event_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        event = Event.query.get_or_404(event_id)

        # Check permissions
        if current_user.role_id not in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
            return jsonify({"error": "Unauthorized"}), 403

        if (
            current_user.role_id == UserRole.ORGANIZER.value
            and event.creator_id != current_user_id
        ):
            return jsonify({"error": "Unauthorized"}), 403

        # Check event status
        if event.status != EventStatus.PUBLISHED:
            return jsonify({"error": "Event cannot be started"}), 400

        # Update event status
        event.status = EventStatus.IN_PROGRESS
        db.session.commit()

        return jsonify({"message": "Event started successfully"})
    except Exception as e:
        db.session.rollback()
        print(f"Error starting event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to start event"}), 500
