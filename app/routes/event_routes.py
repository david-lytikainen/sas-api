from flask import Blueprint, jsonify, request
from app.models.church import Church
from app.models.event import Event
from app.models.user import User
from app.models.event_attendee import EventAttendee
from app.models.event_waitlist import EventWaitlist
from app.models.event_speed_date import EventSpeedDate
from app.models.enums import EventStatus, RegistrationStatus, UserRole, Gender
from app.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_cors import cross_origin
from app.exceptions import UnauthorizedError, MissingFieldsError
from app.services.event_service import EventService
from app.services.payment_service import PaymentService
from app.services.speed_date_service import SpeedDateService
from app.services.event_timer_service import EventTimerService
from datetime import datetime, timedelta, timezone
from flask import current_app
from sqlalchemy import or_

event_bp = Blueprint("event", __name__)

# Apply default rate limit to all routes in this blueprint
# limiter.limit("", apply_defaults=True)(event_bp)


@event_bp.route("/events", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def get_all_events():
    if request.method == "OPTIONS":
        return "", 204

    try:
        verify_jwt_in_request(optional=True)
        current_user_id = get_jwt_identity()
    except Exception:
        current_user_id = None

    events = EventService.get_events()
    
    # If user is authenticated, get their registrations and waitlist status
    user_registrations = {}
    user_waitlist_status = {}
    
    if current_user_id:
        try:
            # Get user's registrations
            registrations = (
                db.session.query(EventAttendee)
                .filter(EventAttendee.user_id == current_user_id)
                .all()
            )
            
            for reg in registrations:
                user_registrations[reg.event_id] = {
                    'status': reg.status.value,
                    'pin': reg.pin,
                    'registration_date': reg.registration_date.isoformat() if reg.registration_date else None,
                    'check_in_date': reg.check_in_date.isoformat() if reg.check_in_date else None,
                    'payment_status': getattr(reg, 'payment_status', 'paid'),  # Default to 'paid' for backward compatibility
                    'payment_due_date': reg.payment_due_date.isoformat() if getattr(reg, 'payment_due_date', None) else None
                }
            
            # Get user's waitlist status
            waitlist_entries = (
                db.session.query(EventWaitlist)
                .filter(EventWaitlist.user_id == current_user_id)
                .all()
            )
            
            for entry in waitlist_entries:
                user_waitlist_status[entry.event_id] = {
                    'status': 'Waitlisted',
                    'waitlisted_at': entry.waitlisted_at.isoformat() if entry.waitlisted_at else None
                }
                
        except Exception as e:
            current_app.logger.error(f"Error fetching user registrations: {str(e)}")
            # Continue without user-specific data if there's an error

    # Convert events to dict format and add user registration info
    events_data = []
    for event in events:
        event_dict = event.to_dict()
        
        # Add user's registration info if available
        if current_user_id:
            if event.id in user_registrations:
                event_dict['registration'] = user_registrations[event.id]
            elif event.id in user_waitlist_status:
                event_dict['registration'] = user_waitlist_status[event.id]
        
        events_data.append(event_dict)

    response_data = {
        'events': events_data
    }
    
    # Add registrations array for backward compatibility
    if current_user_id:
        registrations_array = []
        for event_id, reg_info in user_registrations.items():
            registrations_array.append({
                'event_id': event_id,
                **reg_info
            })
        response_data['registrations'] = registrations_array

    return jsonify(response_data), 200


@event_bp.route("/events", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def create_event():
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Check if user is admin or organizer
    if user.role_id not in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
        return jsonify({"error": "Unauthorized to create events"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Add creator_id to the event data
    data["creator_id"] = current_user_id

    result = EventService.create_event(data)

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result), 201


@event_bp.route("/events/<int:event_id>", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def get_event(event_id):
    if request.method == "OPTIONS":
        return "", 204

    event = EventService.get_event(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    return jsonify(event.to_dict()), 200


@event_bp.route("/events/<int:event_id>", methods=["PUT", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def update_event(event_id):
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get the event to check permissions
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    # Check if user can edit this event
    is_admin = user.role_id == UserRole.ADMIN.value
    is_event_creator = (
        user.role_id == UserRole.ORGANIZER.value and event.creator_id == current_user_id
    )

    if not is_admin and not is_event_creator:
        return jsonify({"error": "Unauthorized to edit this event"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    updated_event, response_body, status_code = EventService.update_event(event_id, data, current_user_id)

    return jsonify(response_body), status_code


@event_bp.route("/events/<int:event_id>", methods=["DELETE", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def delete_event(event_id):
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get the event to check permissions
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    # Check if user can delete this event
    is_admin = user.role_id == UserRole.ADMIN.value
    is_event_creator = (
        user.role_id == UserRole.ORGANIZER.value and event.creator_id == current_user_id
    )

    if not is_admin and not is_event_creator:
        return jsonify({"error": "Unauthorized to delete this event"}), 403

    # Check if event can be safely deleted (no registrations or in progress)
    if event.status in [EventStatus.IN_PROGRESS.value, EventStatus.COMPLETED.value]:
        return (
            jsonify(
                {
                    "error": "Cannot delete events that are in progress or completed"
                }
            ),
            400,
        )

    result = EventService.delete_event(event_id)

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result), 200


@event_bp.route("/events/<int:event_id>/register", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def register_for_event(event_id):
    if request.method == "OPTIONS":
        return "", 204
    current_user_id = get_jwt_identity()
    data = request.get_json() or {}
    join_waitlist_param = data.get("join_waitlist", False)

    # Check if this is a retry after cancellation
    force_registration = data.get("force_registration", False)
    if force_registration:
        current_app.logger.info(f"Force registration requested for user {current_user_id}, event {event_id}")
        EventService.cleanup_user_registration_conflicts(event_id, current_user_id)

    response = EventService.register_for_event(
        event_id, current_user_id, join_waitlist=join_waitlist_param
    )

    # Check if the response contains an error
    if isinstance(response, dict) and "error" in response:
        error_message = response["error"]
        
        # Handle payment required case
        if response.get("requires_payment"):
            return jsonify(response), 402  # Payment Required status code
        elif "Event is currently full" in error_message:
            return jsonify(response), 409
        elif "Registration is closed for this event" in error_message:
            return jsonify(response), 400
        elif "Event is not open for registration" in error_message:
            return jsonify(response), 400
        elif "You are already registered for this event" in error_message:
            return jsonify(response), 400
        elif "You are already on the waitlist for this event" in error_message:
            return (
                jsonify(response),
                400,
            )
        elif "Event with ID" in error_message and "not found" in error_message:
            return jsonify(response), 404
        return jsonify(response), 400

    return (
        jsonify(response),
        200,
    )


@event_bp.route("/events/<int:event_id>/cancel-registration", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def cancel_registration(event_id):
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    data = request.get_json() or {}
    process_refund = data.get("process_refund", True)

    try:
        current_app.logger.info(f"Cancel registration request: user_id={current_user_id}, event_id={event_id}, process_refund={process_refund}")
        response = EventService.cancel_registration(event_id, current_user_id, process_refund)
        current_app.logger.info(f"Cancel registration response: {response}")

        # Check if this is a registration cancellation failure (top-level error)
        if "error" in response and "message" not in response:
            current_app.logger.error(f"Cancel registration error: {response['error']}")
            return jsonify(response), 400

        # If we have a message, the cancellation succeeded (even if refund failed)
        if "message" in response:
            # Log refund issues but still return success for cancellation
            if response.get("refund_info", {}).get("refund_error"):
                current_app.logger.warning(f"Registration cancelled but refund failed: {response['refund_info']['refund_error']}")
            return jsonify(response), 200

        # Fallback for unexpected response format
        current_app.logger.error(f"Unexpected response format: {response}")
        return jsonify({"error": "Unexpected response from cancellation service"}), 500

    except Exception as e:
        current_app.logger.error(f"Cancel registration exception: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to cancel registration"}), 500


@event_bp.route("/events/<int:event_id>/check-in", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def check_in_to_event(event_id):
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    data = request.get_json()

    if not data or "pin" not in data:
        return jsonify({"error": "PIN is required"}), 400

    pin = data["pin"]

    # Find the user's registration
    registration = EventAttendee.query.filter_by(
        event_id=event_id, user_id=current_user_id
    ).first()

    if not registration:
        return jsonify({"error": "You are not registered for this event"}), 400

    if registration.status == RegistrationStatus.CHECKED_IN:
        return jsonify({"error": "You are already checked in"}), 400

    if registration.pin != pin:
        return jsonify({"error": "Invalid PIN"}), 400

    # Update registration status to checked in
    registration.status = RegistrationStatus.CHECKED_IN
    registration.check_in_date = datetime.now(timezone.utc)

    try:
        db.session.commit()
        return jsonify({"message": "Successfully checked in to event"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error checking in user {current_user_id} to event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to check in"}), 500


@event_bp.route("/events/<int:event_id>/status", methods=["PUT", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def update_event_status(event_id):
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get the event to check permissions
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    # Check if user can update this event's status
    is_admin = user.role_id == UserRole.ADMIN.value
    is_event_creator = (
        user.role_id == UserRole.ORGANIZER.value and event.creator_id == current_user_id
    )

    if not is_admin and not is_event_creator:
        return jsonify({"error": "Unauthorized to update event status"}), 403

    data = request.get_json()
    if not data or "status" not in data:
        return jsonify({"error": "Status is required"}), 400

    new_status = data["status"]

    # Validate status
    valid_statuses = [status.value for status in EventStatus]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {valid_statuses}"}), 400

    # Update event status
    event.status = new_status
    event.updated_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
        return jsonify({"message": "Event status updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating event {event_id} status: {str(e)}")
        return jsonify({"error": "Failed to update event status"}), 500


@event_bp.route("/events/<int:event_id>/start", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def start_event(event_id):
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get the event to check permissions
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    # Check if user can start this event
    is_admin = user.role_id == UserRole.ADMIN.value
    is_event_creator = (
        user.role_id == UserRole.ORGANIZER.value and event.creator_id == current_user_id
    )

    if not is_admin and not is_event_creator:
        return jsonify({"error": "Unauthorized to start this event"}), 403

    # Get num_tables and num_rounds from request
    data = request.get_json() or {}
    num_tables = data.get("num_tables", 10)
    num_rounds = data.get("num_rounds", 10)

    try:
        # Update event status to in progress
        event.status = EventStatus.IN_PROGRESS.value
        event.num_tables = num_tables
        event.num_rounds = num_rounds
        event.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Generate speed dating schedules
        from app.services.speed_date_service import SpeedDateService
        result = SpeedDateService.generate_schedules(event_id, num_tables, num_rounds)

        if "error" in result:
            # Revert event status if schedule generation fails
            event.status = EventStatus.REGISTRATION_OPEN.value
            db.session.commit()
            return jsonify(result), 400

        return jsonify({"message": "Event started successfully", "schedules": result}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error starting event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to start event"}), 500


@event_bp.route("/events/<int:event_id>/attendee-pins", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def get_event_attendee_pins(event_id):
    if request.method == "OPTIONS":
        return "", 204

    verify_jwt_in_request()
    current_user_id = get_jwt_identity()

    try:
        # Get the event
        event = Event.query.get_or_404(event_id)

        # Get the user with role preloaded to avoid lazy loading issues
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"error": "User not found"}), 403

        # Check if user has permission to view pins
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)

        if not is_admin and not is_event_creator:
            return jsonify({"error": "Unauthorized to view attendee pins"}), 403

        # Get all attendees with their pins
        attendees = (
            db.session.query(EventAttendee, User)
            .join(User, EventAttendee.user_id == User.id)
            .filter(
                EventAttendee.event_id == event_id,
                EventAttendee.status.in_(
                    [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN, RegistrationStatus.PENDING_PAYMENT]
                ),
            )
            .all()
        )

        attendee_data = [
            {
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "pin": attendee.pin,
                "status": attendee.status.value if attendee.status else None,
                "payment_status": getattr(attendee, 'payment_status', 'paid'),
            }
            for attendee, user in attendees
        ]

        return jsonify(attendee_data), 200
    except Exception as e:
        print(f"Error in get_event_attendee_pins: {str(e)}")
        return jsonify({"error": f"Error retrieving pins: {str(e)}"}), 500


@event_bp.route("/events/<int:event_id>/attendees", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def get_event_attendees(event_id):
    if request.method == "OPTIONS":
        return "", 204

    verify_jwt_in_request()
    current_user_id = get_jwt_identity()

    try:
        # Get the event
        event = Event.query.get_or_404(event_id)

        # Get the user with role preloaded to avoid lazy loading issues
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"error": "User not found"}), 403

        # Check if user has permission to view attendees
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)

        if not is_admin and not is_event_creator:
            return jsonify({"error": "Unauthorized to view attendee information"}), 403

        # Get all attendees with detailed user information
        attendees = (
            db.session.query(EventAttendee, User, Church)
            .join(User, EventAttendee.user_id == User.id)
            .outerjoin(Church, User.church_id == Church.id)
            .filter(
                EventAttendee.event_id == event_id,
                EventAttendee.status.in_(
                    [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN, RegistrationStatus.PENDING_PAYMENT]
                ),
            )
            .all()
        )

        attendee_data = [
            {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "birthday": user.birthday.isoformat() if user.birthday else None,
                "age": user.calculate_age(),
                "gender": user.gender.value if user.gender else None,
                "phone": user.phone,
                "church": church.name if church else "Other",
                "registration_date": (
                    attendee.registration_date.isoformat()
                    if attendee.registration_date
                    else None
                ),
                "check_in_date": (
                    attendee.check_in_date.isoformat()
                    if attendee.check_in_date
                    else None
                ),
                "status": attendee.status.value,
                "pin": attendee.pin,
                "payment_status": getattr(attendee, 'payment_status', 'paid'),
                "payment_due_date": (
                    attendee.payment_due_date.isoformat()
                    if getattr(attendee, 'payment_due_date', None)
                    else None
                ),
            }
            for attendee, user, church in attendees
        ]

        return jsonify(attendee_data), 200
    except Exception as e:
        print(f"Error in get_event_attendees: {str(e)}")
        return jsonify({"error": f"Error retrieving attendees: {str(e)}"}), 500


@event_bp.route("/events/<int:event_id>/pending-payments", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_event_pending_payments(event_id):
    """Get all attendees with pending payments for a specific event"""
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if not current_user:
        return jsonify({"error": "User not found"}), 403

    # Check if user has permission to view pending payments
    event = Event.query.get_or_404(event_id)
    is_admin = current_user.role_id == UserRole.ADMIN.value
    is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and event.creator_id == current_user_id

    if not is_admin and not is_event_creator:
        return jsonify({"error": "Unauthorized to view pending payments"}), 403

    try:
        pending_payments = EventService.get_pending_payments(event_id)
        
        payment_data = [
            {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "phone": user.phone,
                "event_name": event.name,
                "amount_due": float(event.price_per_person),
                "registration_date": attendee.registration_date.isoformat() if attendee.registration_date else None,
                "payment_due_date": attendee.payment_due_date.isoformat() if attendee.payment_due_date else None,
                "status": attendee.status.value,
                "pin": attendee.pin,
            }
            for attendee, user, event in pending_payments
        ]

        return jsonify(payment_data), 200
    except Exception as e:
        current_app.logger.error(f"Error getting pending payments for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to retrieve pending payments"}), 500


@event_bp.route("/pending-payments", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_all_pending_payments():
    """Get all attendees with pending payments across all events"""
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if not current_user:
        return jsonify({"error": "User not found"}), 403

    # Check if user is admin (only admins can see all pending payments)
    if current_user.role_id != UserRole.ADMIN.value:
        return jsonify({"error": "Unauthorized - admin access required"}), 403

    try:
        pending_payments = EventService.get_pending_payments()
        
        payment_data = [
            {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "phone": user.phone,
                "event_id": event.id,
                "event_name": event.name,
                "amount_due": float(event.price_per_person),
                "registration_date": attendee.registration_date.isoformat() if attendee.registration_date else None,
                "payment_due_date": attendee.payment_due_date.isoformat() if attendee.payment_due_date else None,
                "status": attendee.status.value,
                "pin": attendee.pin,
            }
            for attendee, user, event in pending_payments
        ]

        return jsonify(payment_data), 200
    except Exception as e:
        current_app.logger.error(f"Error getting all pending payments: {str(e)}")
        return jsonify({"error": "Failed to retrieve pending payments"}), 500


@event_bp.route("/events/<int:event_id>/mark-payment-completed", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def mark_payment_completed(event_id):
    """Mark a pending payment as completed"""
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    if not current_user:
        return jsonify({"error": "User not found"}), 403

    # Check if user has permission to mark payments as completed
    event = Event.query.get_or_404(event_id)
    is_admin = current_user.role_id == UserRole.ADMIN.value
    is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and event.creator_id == current_user_id

    if not is_admin and not is_event_creator:
        return jsonify({"error": "Unauthorized to mark payments as completed"}), 403

    data = request.get_json()
    if not data or "user_id" not in data:
        return jsonify({"error": "User ID is required"}), 400

    user_id = data["user_id"]

    try:
        result = EventService.mark_payment_completed(event_id, user_id)
        
        if "error" in result:
            return jsonify(result), 400
        
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Error marking payment completed for user {user_id}, event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to mark payment as completed"}), 500


@event_bp.route("/events/<int:event_id>/schedule", methods=["GET"])
@jwt_required()
def get_schedule(event_id):
    current_user_id = get_jwt_identity()

    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)

        # Check if event is in progress or completed
        if event.status not in [
            EventStatus.IN_PROGRESS.value,
            EventStatus.COMPLETED.value,
        ]:
            return (
                jsonify({"error": "Schedule not available. Event has not started"}),
                400,
            )

        # Check if user is registered for this event
        attendee = EventAttendee.query.filter_by(
            event_id=event_id, user_id=current_user_id
        ).first()

        if not attendee:
            return jsonify({"error": "You are not registered for this event"}), 403

        # Get the user's schedule
        schedule = SpeedDateService.get_schedule_for_attendee(event_id, current_user_id)

        if not schedule:
            return (
                jsonify(
                    {"message": "No schedule available. Make sure you are checked in."}
                ),
                404,
            )

        return jsonify({"schedule": schedule}), 200

    except Exception as e:
        print(
            f"Error retrieving schedule for event {event_id}, user {current_user_id}: {str(e)}"
        )
        return jsonify({"error": "Failed to retrieve schedule"}), 500


@event_bp.route("/events/<int:event_id>/all-schedules", methods=["GET"])
@jwt_required()
def get_all_schedules(event_id):
    current_user_id = get_jwt_identity()

    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)

        # Check permissions
        current_user = User.query.get(current_user_id)
        if current_user.role_id not in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
            return jsonify({"error": "Unauthorized"}), 403

        if current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) != str(current_user_id):
            return jsonify({"error": "Unauthorized"}), 403

        # --- Add Logging ---
        current_app.logger.info(
            f"Checking status for event {event_id}. Current status in DB: {event.status}"
        )
        # -------------------

        # Check if event is in progress, or completed
        if event.status not in [
            EventStatus.IN_PROGRESS.value,
            EventStatus.COMPLETED.value,
        ]:
            current_app.logger.warning(
                f"Event {event_id} status '{event.status}' is not valid for viewing schedules. Returning 400."
            )  # Log why it fails
            return (
                jsonify({"error": "Schedule not available. Event has not started"}),
                400,
            )

        # Get all schedules
        schedules = SpeedDateService.get_all_schedules(event_id)

        return jsonify({"schedules": schedules}), 200

    except Exception as e:
        print(f"Error retrieving all schedules for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to retrieve schedules"}), 500


@event_bp.route("/events/<int:event_id>/timer", methods=["GET"])
@jwt_required()
def get_timer_status(event_id):
    current_user_id = get_jwt_identity()
    try:
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({"error": "User not found"}), 403

        try:
            timer_status = EventTimerService.get_timer_status(event_id)
            return jsonify(timer_status), 200
        except Exception as timer_error:
            print(f"Error in timer service: {str(timer_error)}")
            return (
                jsonify(
                    {
                        "has_timer": False,
                        "status": "error",
                        "message": "Timer service error. Please try again later.",
                        "debug_info": str(timer_error),
                    }
                ),
                200,
            )
    except Exception as e:
        print(f"Error retrieving timer status for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to retrieve timer status"}), 500


@event_bp.route("/events/<int:event_id>/timer/start", methods=["POST"])
@jwt_required()
def start_round(event_id):
    current_user_id = get_jwt_identity()

    try:
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({"error": "User not found"}), 403
        is_admin = current_user.role_id == UserRole.ADMIN.value
        if not is_admin:
            return jsonify({"error": "Unauthorized to manage event timer"}), 403

        data = request.get_json() or {}
        round_number = data.get("round_number")

        result = EventTimerService.start_round(event_id, round_number)

        if "error" in result:
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        print(f"Error starting round for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to start round"}), 500


@event_bp.route("/events/<int:event_id>/timer/end", methods=["POST"])
@jwt_required()
def end_round(event_id):
    current_user_id = get_jwt_identity()
    try:
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({"error": "User not found"}), 403

        is_admin = current_user.role_id == UserRole.ADMIN.value
        if not is_admin:
            return jsonify({"error": "Unauthorized to manage event timer"}), 403

        result = EventTimerService.end_round(event_id)

        return jsonify(result.to_dict()), 200

    except Exception as e:
        print(f"Error end round for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to end round"}), 500


@event_bp.route("/events/<int:event_id>/timer/pause", methods=["POST"])
@jwt_required()
def pause_round(event_id):
    current_user_id = get_jwt_identity()

    try:
        event = Event.query.get_or_404(event_id)
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({"error": "User not found"}), 403

        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)
        if not is_admin and not is_event_creator:
            return jsonify({"error": "Unauthorized to manage event timer"}), 403

        data = request.get_json() or {}
        if "time_remaining" not in data:
            return jsonify({"error": "time_remaining is required"}), 400

        time_remaining_raw = data.get("time_remaining")

        try:
            time_remaining = int(time_remaining_raw)
        except (ValueError, TypeError):
            current_app.logger.warning(
                f"Invalid time_remaining value received: {time_remaining_raw}"
            )
            return jsonify({"error": "'time_remaining' must be an integer"}), 400

        current_app.logger.info(
            f"Calling EventTimerService.pause_round for event {event_id} with time {time_remaining}"
        )
        result = EventTimerService.pause_round(event_id, time_remaining)

        if result is None or "error" in result:
            current_app.logger.error(
                f"Error received from EventTimerService.pause_round: {result}"
            )
            return (
                jsonify(
                    result or {"error": "Failed to pause timer in service/repository"}
                ),
                400,
            )
        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(
            f"UNEXPECTED ERROR in pause_round route (event {event_id}): {str(e)}",
            exc_info=True,
        )
        db.session.rollback()
        return (
            jsonify(
                {"error": "An internal server error occurred while pausing the timer"}
            ),
            500,
        )


@event_bp.route("/events/<int:event_id>/timer/resume", methods=["POST"])
@jwt_required()
def resume_round(event_id):
    current_user_id = get_jwt_identity()

    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)

        # Verify user is admin or event creator
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"error": "User not found"}), 403

        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)

        if not is_admin and not is_event_creator:
            return jsonify({"error": "Unauthorized to manage event timer"}), 403

        # Resume the round
        current_app.logger.info(
            f"Calling EventTimerService.resume_round for event {event_id}"
        )
        result = EventTimerService.resume_round(event_id)
        current_app.logger.info(f"EventTimerService.resume_round returned: {result}")

        if result is None or "error" in result:
            current_app.logger.error(
                f"Error received from EventTimerService.resume_round: {result}"
            )
            return (
                jsonify(
                    result or {"error": "Failed to resume timer in service/repository"}
                ),
                400,
            )

        return jsonify(result), 200

    except Exception as e:
        current_app.logger.error(
            f"UNEXPECTED ERROR in resume_round route (event {event_id}): {str(e)}",
            exc_info=True,
        )
        db.session.rollback()  # Attempt rollback
        return (
            jsonify(
                {"error": "An internal server error occurred while resuming the timer"}
            ),
            500,
        )


@event_bp.route("/events/<int:event_id>/timer/next", methods=["POST"])
@jwt_required()
def next_round(event_id):
    current_user_id = get_jwt_identity()

    try:
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({"error": "User not found"}), 403
        is_admin = current_user.role_id == UserRole.ADMIN.value
        if not is_admin:
            return jsonify({"error": "Unauthorized to manage event timer"}), 403

        result = EventTimerService.next_round(event_id)

        if "error" in result:
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        print(f"Error advancing to next round for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to advance to next round"}), 500


@event_bp.route("/events/<int:event_id>/timer/duration", methods=["PUT"])
@jwt_required()
def update_round_duration(event_id):
    current_user_id = get_jwt_identity()

    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)

        # Verify user is admin or event creator
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"error": "User not found"}), 403

        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)

        if not is_admin and not is_event_creator:
            return jsonify({"error": "Unauthorized to manage event timer"}), 403

        # Get round duration from request
        data = request.get_json() or {}

        round_duration = data.get("round_duration")  # Optional
        break_duration = data.get("break_duration")  # Optional

        # Validate that at least one was provided
        if round_duration is None and break_duration is None:
            return (
                jsonify(
                    {"error": "Either round_duration or break_duration is required"}
                ),
                400,
            )

        # Convert to int if provided (handle potential ValueError)
        try:
            if round_duration is not None:
                round_duration = int(round_duration)
            if break_duration is not None:
                break_duration = int(break_duration)
        except (ValueError, TypeError):
            return jsonify({"error": "Durations must be integers"}), 400

        # Update round duration
        result = EventTimerService.update_duration(
            event_id, round_duration, break_duration
        )

        if "error" in result:
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        print(f"Error updating round duration for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to update round duration"}), 500


@event_bp.route("/events/<int:event_id>/round-info", methods=["GET"])
@jwt_required()
def get_round_info(event_id):
    """Get minimal round information for regular attendees"""

    try:
        try:
            # Try to get timer status
            timer_status = EventTimerService.get_timer_status(event_id)

            # Return only round information
            round_info = {
                "has_timer": timer_status.get("has_timer", False),
                "status": timer_status.get("status"),
                "current_round": (
                    timer_status.get("timer", {}).get("current_round")
                    if timer_status.get("timer")
                    else None
                ),
            }

            return jsonify(round_info), 200

        except Exception as timer_error:
            # Fallback if timer service fails
            print(f"Error in timer service for round info: {str(timer_error)}")
            return (
                jsonify(
                    {
                        "has_timer": False,
                        "status": "unknown",
                        "current_round": None,
                        "error": "Timer temporarily unavailable",
                    }
                ),
                200,
            )

    except Exception as e:
        print(f"Error retrieving round info for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to retrieve round information"}), 500


# New route for submitting speed date selections
@event_bp.route(
    "/events/<int:event_id>/speed-date-selections", methods=["POST", "OPTIONS"]
)
@cross_origin(supports_credentials=True)  # If CORS is needed
@jwt_required()
def submit_speed_date_selections(event_id):
    if request.method == "OPTIONS":
        return "", 204

    # Ensure current_user_id is an integer for comparison
    try:
        current_user_id = int(get_jwt_identity())
    except (ValueError, TypeError):
        current_app.logger.error(
            f"Invalid JWT identity type: {get_jwt_identity()}. Expected an integer."
        )
        return jsonify({"error": "Invalid user identity in token."}), 400

    data = request.get_json()
    current_app.logger.info(
        f"User {current_user_id} submitting selections for event {event_id}. Received data: {data}"
    )

    if not data or "selections" not in data or not isinstance(data["selections"], list):
        current_app.logger.warning(
            f"Invalid payload structure from user {current_user_id} for event {event_id}. Data: {data}"
        )
        return (
            jsonify({"error": 'Invalid payload. "selections" array is required.'}),
            400,
        )

    selections = data["selections"]

    try:
        event = Event.query.get_or_404(event_id)
        now_utc = datetime.now(timezone.utc)

        allowed_statuses = [EventStatus.IN_PROGRESS.value]
        is_allowed_status = event.status in allowed_statuses

        is_recently_completed = False
        if event.status == EventStatus.COMPLETED.value:
            # Ensure event.updated_at exists and is datetime object
            if event.updated_at and isinstance(event.updated_at, datetime):
                # Ensure updated_at is timezone-aware (assuming UTC storage or convert)
                updated_at_utc = (
                    event.updated_at.replace(tzinfo=timezone.utc)
                    if event.updated_at.tzinfo is None
                    else event.updated_at
                )
                time_since_completion = now_utc - updated_at_utc
                if time_since_completion <= timedelta(hours=24):
                    is_recently_completed = True
                    current_app.logger.info(
                        f"Event {event_id} completed {time_since_completion} ago, within 24h submission window."
                    )
                else:
                    current_app.logger.warning(
                        f"Event {event_id} completed more than 24 hours ago ({time_since_completion}). Selections closed for user {current_user_id}."
                    )
            else:
                # Log warning if updated_at is missing or not a datetime for a completed event
                current_app.logger.warning(
                    f"Event {event_id} is Completed but has missing or invalid updated_at timestamp ({event.updated_at}). Cannot verify 24-hour submission window."
                )

        current_app.logger.info(
            f"Submission check for event {event_id}: Status='{event.status}'. Allowed Status Check={is_allowed_status}. Recently Completed Check={is_recently_completed}"
        )

        # If neither condition is met, reject the submission
        if not (is_allowed_status or is_recently_completed):
            current_app.logger.warning(
                f"Event {event_id} status '{event.status}' does not allow selections for user {current_user_id} at this time."
            )
            error_message = f"Speed date selections window is closed for this event. Current status: {event.status}"
            if (
                event.status == EventStatus.COMPLETED.value
                and not is_recently_completed
            ):
                error_message = "Speed date selections window closed 24 hours after event completion."
            return jsonify({"error": error_message}), 400

        # Check if user is checked-in attendee
        attendee_record = EventAttendee.query.filter_by(
            event_id=event_id,
            user_id=current_user_id,
            status=RegistrationStatus.CHECKED_IN,
        ).first()
        if not attendee_record:
            current_app.logger.warning(
                f"User {current_user_id} is not a checked-in attendee for event {event_id} or selections not allowed."
            )
            return (
                jsonify(
                    {
                        "error": "User is not a checked-in attendee for this event or selections are not allowed."
                    }
                ),
                403,
            )

        updated_count = 0
        errors = []
        current_app.logger.info(
            f"Processing {len(selections)} selections for event {event_id}, user {current_user_id}."
        )

        for selection_data in selections:
            event_speed_date_id = selection_data.get("event_speed_date_id")
            interested = selection_data.get("interested")

            if (
                event_speed_date_id is None
                or not isinstance(event_speed_date_id, int)
                or interested is None
                or not isinstance(interested, bool)
            ):
                error_detail = f"Invalid selection format for item: {selection_data}"
                current_app.logger.warning(
                    f"Event {event_id}, User {current_user_id}: {error_detail}"
                )
                errors.append(error_detail)
                continue

            speed_date_entry = EventSpeedDate.query.filter_by(
                id=event_speed_date_id, event_id=event_id
            ).first()

            if not speed_date_entry:
                error_detail = f"Speed date entry with ID {event_speed_date_id} not found for event {event_id}."
                current_app.logger.warning(f"User {current_user_id}: {error_detail}")
                errors.append(error_detail)
                continue

            current_app.logger.info(
                f"Participant Check for Speed Date ID {event_speed_date_id}: Comparing current_user_id={current_user_id} against male_id={speed_date_entry.male_id} and female_id={speed_date_entry.female_id}"
            )

            if (
                speed_date_entry.male_id != current_user_id
                and speed_date_entry.female_id != current_user_id
            ):
                error_detail = f"User {current_user_id} is not a participant in speed date ID {event_speed_date_id}."
                current_app.logger.warning(error_detail)
                errors.append(error_detail)
                continue

            try:
                speed_date_entry.record_interest(
                    user_id=current_user_id, interested=interested
                )
                db.session.add(speed_date_entry)
                updated_count += 1
            except ValueError as ve:
                error_detail = f"Error recording interest for speed date ID {event_speed_date_id}: {str(ve)}"
                current_app.logger.warning(f"User {current_user_id}: {error_detail}")
                errors.append(error_detail)
            except Exception as e_inner:
                error_detail = f"Unexpected error for speed date ID {event_speed_date_id}: {str(e_inner)}"
                current_app.logger.error(
                    f"User {current_user_id}: {error_detail}", exc_info=True
                )
                errors.append(error_detail)

        if errors:
            db.session.rollback()
            current_app.logger.warning(
                f"Rolling back due to errors for event {event_id}, user {current_user_id}. Errors: {errors}"
            )
            return (
                jsonify(
                    {
                        "error": "Errors occurred while processing selections.",
                        "details": errors,
                    }
                ),
                400,
            )

        if updated_count == 0 and not errors:
            current_app.logger.info(
                f"No valid selections processed or no changes made for event {event_id}, user {current_user_id}."
            )
            return (
                jsonify(
                    {"message": "No valid selections provided or no changes made."}
                ),
                200,
            )

        db.session.commit()
        current_app.logger.info(
            f"User {current_user_id} successfully submitted {updated_count} selections for event {event_id}."
        )
        return (
            jsonify(
                {
                    "message": f"{updated_count} speed date selections recorded successfully."
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Outer exception submitting speed date selections for event {event_id}, user {current_user_id}: {str(e)}",
            exc_info=True,
        )
        return jsonify({"error": "Failed to submit speed date selections."}), 500


@event_bp.route("/events/<int:event_id>/my-matches", methods=["GET"])
@jwt_required()
def get_my_matches(event_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User not found or token invalid"}), 401

    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    if event.status != EventStatus.COMPLETED.value:
        return (
            jsonify(
                {"error": "Matches are only available after the event is completed."}
            ),
            400,
        )
    else:
        # Event is completed, check if 24 hours have passed since completion
        now_utc = datetime.now(timezone.utc)
        if event.updated_at and isinstance(event.updated_at, datetime):
            updated_at_utc = (
                event.updated_at.replace(tzinfo=timezone.utc)
                if event.updated_at.tzinfo is None
                else event.updated_at
            )
            time_since_completion = now_utc - updated_at_utc

            if time_since_completion < timedelta(hours=24):
                # Less than 24 hours have passed
                current_app.logger.info(
                    f"Match request for completed event {event_id} denied. Only {time_since_completion} has passed."
                )
                return (
                    jsonify(
                        {
                            "error": "Matches will be available 24 hours after event completion."
                        }
                    ),
                    403,
                )
            # Else (24 hours or more have passed), proceed to fetch matches below
            current_app.logger.info(
                f"Match request for completed event {event_id} allowed. {time_since_completion} has passed."
            )
        else:
            # Handle case where completed event is missing a valid updated_at timestamp
            current_app.logger.error(
                f"Cannot determine match availability for completed event {event_id}: missing or invalid updated_at ({event.updated_at})"
            )
            return (
                jsonify(
                    {
                        "error": "Cannot determine match availability time due to missing event completion data."
                    }
                ),
                500,
            )

    attendee_record = EventAttendee.query.filter(
        EventAttendee.event_id == event_id,
        EventAttendee.user_id == current_user_id,
        EventAttendee.status == RegistrationStatus.CHECKED_IN,
    ).first()

    if not attendee_record:
        return (
            jsonify({"error": "You were not checked in for this event."}),
            403,
        )  # Changed error msg slightly

    mutual_matches_query = EventSpeedDate.query.filter(
        EventSpeedDate.event_id == event_id,
        EventSpeedDate.male_interested == True,
        EventSpeedDate.female_interested == True,
        or_(
            EventSpeedDate.male_id == current_user_id,
            EventSpeedDate.female_id == current_user_id,
        ),
    ).all()

    matches_details = []
    if mutual_matches_query:
        matched_partner_ids = set()
        for record in mutual_matches_query:
            partner_id = (
                record.female_id
                if record.male_id == current_user_id
                else record.male_id
            )
            matched_partner_ids.add(partner_id)

        if matched_partner_ids:
            matched_users = User.query.filter(User.id.in_(matched_partner_ids)).all()
            for matched_user in matched_users:
                matches_details.append(
                    {
                        "id": matched_user.id,
                        "first_name": matched_user.first_name,
                        "last_name": matched_user.last_name,
                        "email": matched_user.email,
                        "age": matched_user.calculate_age(),
                        "gender": (
                            matched_user.gender.value if matched_user.gender else None
                        ),
                    }
                )

    return jsonify({"matches": matches_details}), 200


@event_bp.route("/events/<int:event_id>/all-matches", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_all_matches_for_event(event_id):
    """Get all mutual matches for an event - admin/organizer only"""
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()

    try:
        event = Event.query.get_or_404(event_id)

        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"error": "User not found"}), 403

        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)

        if not is_admin and not is_event_creator:
            return jsonify({"error": "Unauthorized to view all event matches"}), 403

        if event.status not in [
            EventStatus.IN_PROGRESS.value,
            EventStatus.COMPLETED.value,
        ]:
            return (
                jsonify(
                    {"error": "Matches are only available for events that have started"}
                ),
                400,
            )

        mutual_matches_query = EventSpeedDate.query.filter(
            EventSpeedDate.event_id == event_id,
            EventSpeedDate.male_interested == True,
            EventSpeedDate.female_interested == True,
        ).all()

        matches_details = []
        if mutual_matches_query:
            user_ids = set()
            for record in mutual_matches_query:
                user_ids.add(record.male_id)
                user_ids.add(record.female_id)

            users_dict = {
                user.id: user for user in User.query.filter(User.id.in_(user_ids)).all()
            }

            for record in mutual_matches_query:
                male_user = users_dict.get(record.male_id)
                female_user = users_dict.get(record.female_id)

                if male_user and female_user:
                    matches_details.append(
                        {
                            "user1_name": f"{male_user.first_name} {male_user.last_name}",
                            "user1_email": male_user.email,
                            "user2_name": f"{female_user.first_name} {female_user.last_name}",
                            "user2_email": female_user.email,
                        }
                    )

            matches_details.sort(
                key=lambda x: (x["user1_name"].lower(), x["user2_name"].lower())
            )

        current_app.logger.info(
            f"Admin/organizer {current_user_id} viewed {len(matches_details)} matches for event {event_id}"
        )
        return jsonify({"matches": matches_details}), 200

    except Exception as e:
        current_app.logger.error(
            f"Error retrieving all matches for event {event_id}: {str(e)}",
            exc_info=True,
        )
        return jsonify({"error": "Failed to retrieve matches"}), 500


@event_bp.route("/events/<int:event_id>", methods=["DELETE", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def delete_event_route(event_id):
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()

    try:
        response_message, status_code = EventService.delete_event(
            event_id, current_user_id
        )
        return jsonify(response_message), status_code
    except UnauthorizedError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        # db.session.rollback() # Rollback is handled in repository or should be if critical
        current_app.logger.error(
            f"Error deleting event {event_id}: {str(e)}", exc_info=True
        )
        return jsonify({"error": "Failed to delete event"}), 500


@event_bp.route("/events/<int:event_id>/waitlist", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_event_waitlist(event_id):
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()

    try:
        event = Event.query.get_or_404(event_id)
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"error": "User not found"}), 403

        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)

        if not is_admin and not is_event_creator:
            return jsonify({"error": "Unauthorized to view event waitlist"}), 403

        waitlist_entries = (
            db.session.query(EventWaitlist, User, Church)
            .join(User, EventWaitlist.user_id == User.id)
            .outerjoin(Church, User.church_id == Church.id)
            .filter(EventWaitlist.event_id == event_id)
            .order_by(EventWaitlist.waitlisted_at.asc())
            .all()
        )

        waitlist_data = [
            {
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "birthday": user.birthday.isoformat() if user.birthday else None,
                "age": user.calculate_age(),
                "gender": user.gender.value if user.gender else None,
                "phone": user.phone,
                "church": church.name if church else "Other",
                "waitlisted_at": (
                    wl_entry.waitlisted_at.isoformat()
                    if wl_entry.waitlisted_at
                    else None
                ),
                "status": "Waitlisted",  # Explicitly set status
            }
            for wl_entry, user, church in waitlist_entries
        ]
        return jsonify(waitlist_data), 200

    except Exception as e:
        current_app.logger.error(
            f"Error retrieving waitlist for event {event_id}: {str(e)}", exc_info=True
        )
        return jsonify({"error": f"Error retrieving waitlist: {str(e)}"}), 500


@event_bp.route("/stripe/config", methods=["GET"])
def get_stripe_config():
    """Get Stripe publishable key for frontend"""
    try:
        config = PaymentService.get_stripe_config()
        return jsonify(config), 200
    except Exception as e:
        current_app.logger.error(f"Error getting Stripe config: {str(e)}")
        return jsonify({"error": "Unable to get payment configuration"}), 500


@event_bp.route("/events/<int:event_id>/create-checkout-session", methods=["POST"])
@jwt_required()
def create_checkout_session(event_id):
    """Create a Stripe checkout session for event registration"""
    try:
        current_user_id = get_jwt_identity()
        
        # Create checkout session
        result, status_code = PaymentService.create_checkout_session(event_id, current_user_id)
        
        return jsonify(result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Error creating checkout session: {str(e)}")
        return jsonify({"error": "Unable to create payment session"}), 500


@event_bp.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events"""
    try:
        payload = request.get_data(as_text=True)
        signature = request.headers.get("Stripe-Signature")
        
        if not signature:
            current_app.logger.error("Missing Stripe signature")
            return jsonify({"error": "Missing signature"}), 400
        
        result, status_code = PaymentService.handle_webhook_event(payload, signature)
        return jsonify(result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Error handling Stripe webhook: {str(e)}")
        return jsonify({"error": "Webhook processing failed"}), 500


@event_bp.route("/stripe/verify-session/<session_id>", methods=["GET"])
@jwt_required()
def verify_payment_session(session_id):
    """Verify a Stripe payment session"""
    try:
        result, status_code = PaymentService.verify_payment_session(session_id)
        return jsonify(result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Error verifying payment session: {str(e)}")
        return jsonify({"error": "Unable to verify payment"}), 500


@event_bp.route("/events/<int:event_id>/create-payment-intent", methods=["POST"])
@jwt_required()
def create_payment_intent(event_id):
    """Create a Stripe PaymentIntent for native payment form"""
    try:
        current_user_id = get_jwt_identity()
        
        # Create PaymentIntent
        result, status_code = PaymentService.create_payment_intent(event_id, current_user_id)
        
        return jsonify(result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Error creating PaymentIntent: {str(e)}")
        return jsonify({"error": "Unable to create payment intent"}), 500


@event_bp.route("/stripe/payment-intent/<payment_intent_id>", methods=["GET"])
@jwt_required()
def get_payment_intent(payment_intent_id):
    """Retrieve an existing PaymentIntent's client_secret for waitlist payments"""
    try:
        current_user_id = get_jwt_identity()
        
        # Get the PaymentIntent from Stripe to retrieve the client_secret
        import stripe
        
        # Ensure Stripe API key is set
        PaymentService._ensure_stripe_key()
        
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        # Verify this PaymentIntent belongs to the current user by checking metadata
        if payment_intent.metadata.get('user_id') != str(current_user_id):
            return jsonify({"error": "Unauthorized access to payment intent"}), 403

        # If payment succeeded but user is not yet registered, register now
        if payment_intent.status == 'succeeded':
            try:
                event_id_meta = payment_intent.metadata.get('event_id')
                if event_id_meta:
                    from app.repositories.event_attendee_repository import EventAttendeeRepository
                    event_id_int = int(event_id_meta)
                    already = EventAttendeeRepository.find_by_event_and_user(event_id_int, current_user_id)
                    if not already:
                        from app.services.event_service import EventService
                        current_app.logger.info(f"Auto-registering user {current_user_id} for event {event_id_int} after successful PaymentIntent fetch")
                        result = EventService.register_for_event(event_id_int, current_user_id, join_waitlist=False, payment_completed=True)
                        if "error" in result:
                            current_app.logger.error(f"Auto-registration failed for user {current_user_id}, event {event_id_int}: {result['error']}")
                        else:
                            current_app.logger.info(f"Auto-registration successful for user {current_user_id}, event {event_id_int}: {result}")
                    else:
                        current_app.logger.info(f"User {current_user_id} already registered for event {event_id_int}, skipping auto-registration")
                else:
                    current_app.logger.warning(f"No event_id found in PaymentIntent {payment_intent_id} metadata")
            except Exception as e:
                current_app.logger.error(f"Error auto-registering after PaymentIntent fetch: {str(e)}", exc_info=True)

        return jsonify({
            "client_secret": payment_intent.client_secret,
            "status": payment_intent.status,
            "amount": payment_intent.amount
        }), 200
        
    except stripe.error.InvalidRequestError:
        return jsonify({"error": "Payment intent not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error retrieving PaymentIntent: {str(e)}")
        return jsonify({"error": "Failed to retrieve payment intent"}), 500


@event_bp.route("/events/<int:event_id>/register-from-waitlist", methods=["POST"])
@jwt_required()
def register_from_waitlist_route(event_id):
    current_user_id = get_jwt_identity()
    
    response = EventService.register_from_waitlist(event_id, current_user_id, payment_completed=True)
    
    if "error" in response:
        return jsonify(response), 400
    else:
        return jsonify(response), 200


# Refund-related routes
@event_bp.route("/events/<int:event_id>/refund-policy", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_refund_policy(event_id):
    if request.method == "OPTIONS":
        return "", 204
        
    try:
        from app.services.payment_service import PaymentService
        
        policy_result, status_code = PaymentService.get_refund_policy_info(event_id)
        return jsonify(policy_result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Error getting refund policy for event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to get refund policy"}), 500


@event_bp.route("/events/<int:event_id>/process-refund", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def process_manual_refund(event_id):
    if request.method == "OPTIONS":
        return "", 204
        
    current_user_id = get_jwt_identity()
    data = request.get_json() or {}
    
    # Optional: Allow admin to process refunds for other users
    target_user_id = data.get('user_id', current_user_id)
    reason = data.get('reason', 'requested_by_customer')
    
    # Check if current user can process refund for target user
    if target_user_id != current_user_id:
        current_user = User.query.get(current_user_id)
        if not current_user or current_user.role_id != UserRole.ADMIN.value:
            return jsonify({"error": "Unauthorized to process refund for other users"}), 403
    
    try:
        from app.services.payment_service import PaymentService
        
        refund_result, status_code = PaymentService.process_refund(event_id, target_user_id, reason)
        return jsonify(refund_result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Error processing refund for user {target_user_id}, event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to process refund"}), 500


@event_bp.route("/events/<int:event_id>/payment-info", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_payment_info(event_id):
    if request.method == "OPTIONS":
        return "", 204
        
    current_user_id = get_jwt_identity()
    
    try:
        from app.services.payment_service import PaymentService
        
        payment_info = PaymentService.find_payment_for_registration(event_id, current_user_id)
        
        if payment_info:
            # Remove sensitive information before sending to frontend
            safe_payment_info = {
                "has_payment": True,
                "amount": payment_info.get('amount', 0) / 100,  # Convert from cents
                "currency": payment_info.get('currency', 'usd'),
                "status": payment_info.get('status'),
                "payment_date": payment_info.get('created')
            }
            return jsonify(safe_payment_info), 200
        else:
            return jsonify({"has_payment": False}), 200
            
    except Exception as e:
        current_app.logger.error(f"Error getting payment info for user {current_user_id}, event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to get payment information"}), 500


# Venmo Payment Routes
@event_bp.route("/events/<int:event_id>/create-venmo-payment-intent", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def create_venmo_payment_intent(event_id):
    """Create a Stripe PaymentIntent specifically for Venmo payments"""
    if request.method == "OPTIONS":
        return "", 204
        
    try:
        current_user_id = get_jwt_identity()
        
        # Create Venmo PaymentIntent
        result, status_code = PaymentService.create_venmo_payment_intent(event_id, current_user_id)
        
        return jsonify(result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Error creating Venmo PaymentIntent: {str(e)}")
        return jsonify({"error": "Unable to create Venmo payment intent"}), 500


@event_bp.route("/venmo/confirm-payment/<payment_intent_id>", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def confirm_venmo_payment(payment_intent_id):
    """Confirm a Venmo payment after user completes payment in Venmo app"""
    if request.method == "OPTIONS":
        return "", 204
        
    try:
        data = request.get_json() or {}
        venmo_transaction_id = data.get('venmo_transaction_id')
        
        result, status_code = PaymentService.confirm_venmo_payment(payment_intent_id, venmo_transaction_id)
        
        return jsonify(result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Error confirming Venmo payment: {str(e)}")
        return jsonify({"error": "Unable to confirm Venmo payment"}), 500


@event_bp.route("/venmo/simulate-payment/<payment_intent_id>", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
def simulate_venmo_payment(payment_intent_id):
    """Simulate Venmo payment completion for testing purposes"""
    if request.method == "OPTIONS":
        return "", 204
        
    try:
        # Only allow in development mode
        if not current_app.config.get("DEBUG", False):
            return jsonify({"error": "Simulation only available in development mode"}), 403
            
        result, status_code = PaymentService.simulate_venmo_payment_completion(payment_intent_id)
        
        return jsonify(result), status_code
        
    except Exception as e:
        current_app.logger.error(f"Error simulating Venmo payment: {str(e)}")
        return jsonify({"error": "Unable to simulate Venmo payment"}), 500


@event_bp.route("/venmo/payment-status/<payment_intent_id>", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_venmo_payment_status(payment_intent_id):
    """Get the status of a Venmo payment"""
    if request.method == "OPTIONS":
        return "", 204
        
    try:
        current_user_id = get_jwt_identity()
        
        # Get the PaymentIntent from Stripe to check status
        import stripe
        
        PaymentService._ensure_stripe_key()
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        # Verify this PaymentIntent belongs to the current user by checking metadata
        if payment_intent.metadata.get('user_id') != str(current_user_id):
            return jsonify({"error": "Unauthorized access to payment intent"}), 403
            
        return jsonify({
            "payment_intent_id": payment_intent.id,
            "status": payment_intent.status,
            "amount": payment_intent.amount,
            "currency": payment_intent.currency,
            "payment_method": payment_intent.metadata.get('payment_method', 'unknown'),
            "event_id": payment_intent.metadata.get('event_id'),
            "event_name": payment_intent.metadata.get('event_name')
        }), 200
        
    except stripe.error.InvalidRequestError:
        return jsonify({"error": "Payment intent not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error getting Venmo payment status: {str(e)}")
        return jsonify({"error": "Failed to get payment status"}), 500
