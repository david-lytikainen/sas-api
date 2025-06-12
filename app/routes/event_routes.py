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
from app.services.speed_date_service import SpeedDateService
from app.services.event_timer_service import EventTimerService
from datetime import datetime, timedelta, timezone
from flask import current_app
from sqlalchemy import or_

event_bp = Blueprint("event", __name__)

# Apply default rate limit to all routes in this blueprint
# limiter.limit("", apply_defaults=True)(event_bp)


@event_bp.route("/events", methods=["GET", "OPTIONS"])
def get_events():
    if request.method == "OPTIONS":
        return "", 204

    verify_jwt_in_request()
    user_id = get_jwt_identity()

    # Get all events
    events_data = EventService.get_events_for_user(user_id)

    # Get user's actual registrations (excluding cancelled ones)
    user_registrations = EventAttendee.query.filter(
        EventAttendee.user_id == user_id,
        EventAttendee.status != RegistrationStatus.CANCELLED
    ).all()
    registrations_map = {
        reg.event_id: {
            "event_id": reg.event_id,
            "status": reg.status.value,
            "pin": reg.pin,
            "registration_date": (
                reg.registration_date.isoformat() if reg.registration_date else None
            ),
            "check_in_date": (
                reg.check_in_date.isoformat() if reg.check_in_date else None
            ),
        }
        for reg in user_registrations
    }

    # Get user's waitlist entries
    user_waitlist_entries = EventWaitlist.query.filter_by(user_id=user_id).all()
    for wl_entry in user_waitlist_entries:
        if wl_entry.event_id not in registrations_map:
            registrations_map[wl_entry.event_id] = {
                "event_id": wl_entry.event_id,
                "status": RegistrationStatus.WAITLISTED.value,
                "pin": None,
                "registration_date": (
                    wl_entry.waitlisted_at.isoformat()
                    if wl_entry.waitlisted_at
                    else None
                ),
                "check_in_date": None,
            }

    final_registrations_data = list(registrations_map.values())

    # Return both events and comprehensive registrations data
    return jsonify({"events": events_data, "registrations": final_registrations_data})


@event_bp.route("/events/<int:event_id>", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def get_event_by_id(event_id):
    if request.method == "OPTIONS":
        return "", 204

    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()

        # Get the specific event
        event = Event.query.get_or_404(event_id)
        event_data = event.to_dict()

        # Check if user is registered for this event
        registration = EventAttendee.query.filter_by(
            user_id=user_id, event_id=event_id
        ).first()

        if registration:
            registration_data = {
                "status": registration.status.value,
                "pin": registration.pin,
                "registration_date": (
                    registration.registration_date.isoformat()
                    if registration.registration_date
                    else None
                ),
                "check_in_date": (
                    registration.check_in_date.isoformat()
                    if registration.check_in_date
                    else None
                ),
            }
            event_data["registration"] = registration_data

        return jsonify(event_data)
    except Exception as e:
        print(f"Error fetching event {event_id}: {str(e)}")
        return jsonify({"error": "Failed to fetch event details"}), 500


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
        return jsonify({"error": f"Failed to create event: {e}"}), 500


@event_bp.route("/events/<int:event_id>", methods=["PUT", "OPTIONS"])
@cross_origin(supports_credentials=True)
@jwt_required()
def update_event_details_route(event_id):
    if request.method == "OPTIONS":
        return "", 204

    current_user_id = get_jwt_identity()
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    try:
        updated_event, message, status_code = EventService.update_event(
            event_id, data, current_user_id
        )
        if updated_event:
            return (
                jsonify(
                    {"message": message["message"], "event": updated_event.to_dict()}
                ),
                status_code,
            )
        else:
            return jsonify(message), status_code  # Error message from service
    except UnauthorizedError as e:
        return jsonify({"error": str(e)}), 403
    except (
        MissingFieldsError
    ) as e:  # Should not be hit if service handles this, but good practice
        return (
            jsonify({"error": "Missing required fields", "missing_fields": e.fields}),
            400,
        )
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error updating event {event_id}: {str(e)}", exc_info=True
        )
        return jsonify({"error": "Failed to update event"}), 500


@event_bp.route("/events/<int:event_id>/register", methods=["POST"])
@jwt_required()
def register_for_event(event_id):
    current_user_id = get_jwt_identity()
    data = request.get_json() or {}
    join_waitlist_param = data.get("join_waitlist", False)

    response = EventService.register_for_event(
        event_id, current_user_id, join_waitlist=join_waitlist_param
    )

    # Check if the response contains an error
    if isinstance(response, dict) and "error" in response:
        error_message = response["error"]
        if "Event is currently full" in error_message:
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


@event_bp.route(
    "/events/<int:event_id>/cancel-registration", methods=["POST", "OPTIONS"]
)
def cancel_registration(event_id):
    if request.method == "OPTIONS":
        return "", 204

    verify_jwt_in_request()
    user_id = get_jwt_identity()
    response = EventService.cancel_registration(event_id, user_id)
    return jsonify(response)


@event_bp.route("/events/<int:event_id>/generate/schedules", methods=["POST"])
@cross_origin(supports_credentials=True)
@jwt_required()
def generate_schedules(event_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        event = Event.query.get_or_404(event_id)

        data = request.get_json() or {}
        num_tables = data.get("num_tables", 15)
        num_rounds = data.get("num_rounds", 15)

        try:
            num_tables = int(num_tables)
            num_rounds = int(num_rounds)

            if num_tables < 1 or num_rounds < 1:
                return (
                    jsonify(
                        {
                            "error": "Number of tables and rounds must be positive integers"
                        }
                    ),
                    400,
                )
        except (ValueError, TypeError):
            return (
                jsonify(
                    {"error": "Invalid input for tables or rounds, must be integers"}
                ),
                400,
            )

        if current_user.role_id not in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
            return jsonify({"error": "Unauthorized"}), 403
        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return (
                jsonify(
                    {"error": "Event cannot be started (must be Registration Open)"}
                ),
                400,
            )

        num_rounds_actual, num_tables_actual = SpeedDateService.generate_schedule(
            event_id, num_tables, num_rounds
        )

        if num_rounds_actual > 0:
            event.status = EventStatus.IN_PROGRESS.value
            event.num_rounds = num_rounds_actual
            event.num_tables = num_tables_actual
            db.session.commit()
            EventTimerService.delete_timer(event_id)
            EventTimerService.create_timer(event_id)
            current_app.logger.info(f"Event {event_id} status set to IN_PROGRESS.")
            return jsonify({"message": "Event schedule generated"})
        else:
            current_app.logger.warning(f"Event {event_id} schedule generation failed")
            return jsonify({"message": "Event schedule could not be generated."})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error starting event {event_id}: {str(e)}", exc_info=True
        )
        return jsonify({"error": "Failed to start event"}), 500


@event_bp.route("/events/<int:event_id>/check-in", methods=["POST"])
@jwt_required()
def check_in(event_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()

    if not data or "pin" not in data:
        return jsonify({"error": "Missing PIN"}), 400

    pin = data["pin"]

    response, status_code = EventService.check_in(event_id, current_user_id, pin)
    return jsonify(response), status_code


@event_bp.route("/events/<int:event_id>/status", methods=["PATCH", "OPTIONS"])
@cross_origin(supports_credentials=True)
def update_event_status(event_id):
    if request.method == "OPTIONS":
        return "", 204

    verify_jwt_in_request()
    current_user_id = get_jwt_identity()
    data = request.get_json()

    # Validate the request
    if not data or "status" not in data:
        return jsonify({"error": "Missing status"}), 400

    status = data["status"]

    try:
        # Validate status values
        valid_statuses = [status.value for status in EventStatus]
        if status not in valid_statuses:
            return (
                jsonify(
                    {
                        "error": f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
                    }
                ),
                400,
            )

        # Get the event
        event = Event.query.get_or_404(event_id)

        # Get the user with role preloaded to avoid lazy loading issues
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"error": "User not found"}), 403

        # Check if user has permission to update the event
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)

        if not is_admin and not is_event_creator:
            return jsonify({"error": "Unauthorized to update this event"}), 403

        # Store the current status before changing it
        original_status = event.status

        # Check if status is actually changing
        if original_status == status:
            return (
                jsonify({"message": "Event status is already " + status}),
                200,
            )  # Or maybe 304 Not Modified

        # Now we can directly assign the status string
        event.status = status
        db.session.commit()
        current_app.logger.info(
            f"Successfully updated event {event_id} status from '{original_status}' to '{status}'"
        )
        return jsonify({"message": "Event status updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_event_status: {str(e)}")
        return jsonify({"error": f"Error updating status: {str(e)}"}), 500


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
                    [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
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

        # Get all attendees with detailed user information (including cancelled for analytics)
        attendees = (
            db.session.query(EventAttendee, User, Church)
            .join(User, EventAttendee.user_id == User.id)
            .outerjoin(Church, User.church_id == Church.id)
            .filter(
                EventAttendee.event_id == event_id,
                EventAttendee.status.in_(
                    [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN, RegistrationStatus.CANCELLED]
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
            }
            for attendee, user, church in attendees
        ]

        return jsonify(attendee_data), 200
    except Exception as e:
        print(f"Error in get_event_attendees: {str(e)}")
        return jsonify({"error": f"Error retrieving attendees: {str(e)}"}), 500


@event_bp.route(
    "/events/<int:event_id>/attendees/<int:attendee_id>", methods=["PATCH", "OPTIONS"]
)
@cross_origin(supports_credentials=True)
def update_attendee_details(event_id, attendee_id):
    if request.method == "OPTIONS":
        return "", 204

    verify_jwt_in_request()
    current_user_id = get_jwt_identity()

    try:
        # Get the event
        event = Event.query.get_or_404(event_id)

        # Get the user and verify permissions
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"error": "User not found"}), 403

        # Check if user has permission to update attendees
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)

        if not is_admin and not is_event_creator:
            return (
                jsonify({"error": "Unauthorized to update attendee information"}),
                403,
            )

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No update data provided"}), 400

        # Get the user to update
        user_to_update = User.query.get_or_404(attendee_id)

        # Also verify this user is actually registered for this event
        attendee = EventAttendee.query.filter_by(
            event_id=event_id, user_id=attendee_id
        ).first()
        if not attendee:
            return jsonify({"error": "User is not registered for this event"}), 404

        # Track which fields were updated
        updated_fields = []

        # Update user fields if provided
        if "first_name" in data and data["first_name"]:
            user_to_update.first_name = data["first_name"]
            updated_fields.append("first_name")

        if "last_name" in data and data["last_name"]:
            user_to_update.last_name = data["last_name"]
            updated_fields.append("last_name")

        if "email" in data and data["email"]:
            user_to_update.email = data["email"]
            updated_fields.append("email")

        if "phone" in data and data["phone"]:
            user_to_update.phone = data["phone"]
            updated_fields.append("phone")

        if "gender" in data and data["gender"]:
            try:
                user_to_update.gender = Gender[data["gender"].upper()]
                updated_fields.append("gender")
            except KeyError:
                return (
                    jsonify(
                        {"error": "Invalid gender value. Must be either MALE or FEMALE"}
                    ),
                    400,
                )

        if "birthday" in data and data["birthday"]:
            try:
                user_to_update.birthday = datetime.strptime(
                    data["birthday"], "%Y-%m-%d"
                ).date()
                updated_fields.append("birthday")
            except ValueError:
                return (
                    jsonify({"error": "Invalid birthday format. Use YYYY-MM-DD"}),
                    400,
                )
        if "church" in data and data["church"]:
            try:
                church_input = data["church"]
                church = None

                # Try to parse as integer first (church ID)
                try:
                    church_id = int(church_input)
                    church = Church.query.get(church_id)
                except (ValueError, TypeError):
                    # If it's not an integer, treat it as a church name
                    church = Church.query.filter_by(name=church_input).first()

                if church:
                    user_to_update.church_id = church.id
                    updated_fields.append("church")
                else:
                    # If church not found, create a new one
                    church = Church(name=church_input)
                    db.session.add(church)
                    db.session.commit()
                    user_to_update.church_id = church.id
                    updated_fields.append("church")

            except Exception as e:
                return jsonify({"error": f"Error updating church: {str(e)}"}), 500

        # Update attendee fields
        if "pin" in data and data["pin"]:
            attendee.pin = data["pin"]
            updated_fields.append("pin")

        # Save changes if any fields were updated
        if updated_fields:
            db.session.commit()

            # Refresh the user_to_update object to get the latest church data
            db.session.refresh(user_to_update)

            # Get updated attendee data to return to frontend
            church_name = "Other"
            if user_to_update.church_id:
                church = Church.query.get(user_to_update.church_id)
                if church:
                    church_name = church.name

            updated_attendee_data = {
                "id": user_to_update.id,
                "name": f"{user_to_update.first_name} {user_to_update.last_name}",
                "email": user_to_update.email,
                "first_name": user_to_update.first_name,
                "last_name": user_to_update.last_name,
                "birthday": (
                    user_to_update.birthday.isoformat()
                    if user_to_update.birthday
                    else None
                ),
                "age": user_to_update.calculate_age(),
                "gender": (
                    user_to_update.gender.value if user_to_update.gender else None
                ),
                "phone": user_to_update.phone,
                "church": church_name,
                "pin": attendee.pin,
            }

            return (
                jsonify(
                    {
                        "message": "Attendee details updated successfully",
                        "updated_fields": updated_fields,
                        "attendee": updated_attendee_data,
                    }
                ),
                200,
            )
        else:
            return jsonify({"message": "No fields were updated"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error updating attendee details: {str(e)}")
        return jsonify({"error": f"Error updating attendee: {str(e)}"}), 500


@event_bp.route(
    "/events/<int:event_id>/waitlist/<int:user_id>", methods=["PATCH", "OPTIONS"]
)
@cross_origin(supports_credentials=True)
@jwt_required()
def update_waitlist_attendee_details(event_id, user_id):
    if request.method == "OPTIONS":
        return "", 204

    verify_jwt_in_request()
    current_user_id = get_jwt_identity()

    try:
        # Get the event
        event = Event.query.get_or_404(event_id)

        # Get the user and verify permissions
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"error": "User not found"}), 403

        # Check if user has permission to update attendees
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(
            event.creator_id
        ) == str(current_user_id)

        if not is_admin and not is_event_creator:
            return (
                jsonify(
                    {"error": "Unauthorized to update waitlist attendee information"}
                ),
                403,
            )

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No update data provided"}), 400

        # Get the user to update
        user_to_update = User.query.get_or_404(user_id)

        # Also verify this user is actually waitlisted for this event
        waitlist_entry = EventWaitlist.query.filter_by(
            event_id=event_id, user_id=user_id
        ).first()
        if not waitlist_entry:
            return jsonify({"error": "User is not waitlisted for this event"}), 404

        # Track which fields were updated
        updated_fields = []

        # Update user fields if provided
        if "first_name" in data and data["first_name"]:
            user_to_update.first_name = data["first_name"]
            updated_fields.append("first_name")

        if "last_name" in data and data["last_name"]:
            user_to_update.last_name = data["last_name"]
            updated_fields.append("last_name")

        if "email" in data and data["email"]:
            user_to_update.email = data["email"]
            updated_fields.append("email")

        if "phone" in data and data["phone"]:
            user_to_update.phone = data["phone"]
            updated_fields.append("phone")

        if "gender" in data and data["gender"]:
            try:
                user_to_update.gender = Gender[data["gender"].upper()]
                updated_fields.append("gender")
            except KeyError:
                return (
                    jsonify(
                        {"error": "Invalid gender value. Must be either MALE or FEMALE"}
                    ),
                    400,
                )
        if "birthday" in data and data["birthday"]:
            try:
                user_to_update.birthday = datetime.strptime(
                    data["birthday"], "%Y-%m-%d"
                ).date()
                updated_fields.append("birthday")
            except (ValueError, TypeError):
                return (
                    jsonify(
                        {"error": "Invalid birthday format. Use YYYY-MM-DD string"}
                    ),
                    400,
                )
        if "church" in data and data["church"]:
            try:
                church_input = data["church"]
                church = None

                if isinstance(church_input, int):
                    church = Church.query.get(church_input)
                elif isinstance(church_input, str):
                    church = Church.query.filter_by(name=church_input).first()
                    if not church and church_input:
                        church = Church(name=church_input)
                        db.session.add(church)
                        db.session.flush()

                if church:
                    user_to_update.church_id = church.id
                    updated_fields.append("church")
                elif not church_input:
                    user_to_update.church_id = None
                    updated_fields.append("church")

            except Exception as e:
                current_app.logger.error(
                    f"Error updating church for waitlist user {user_id} in event {event_id}: {str(e)}"
                )
                return jsonify({"error": f"Error updating church: {str(e)}"}), 500

        # Save changes if any fields were updated
        if updated_fields:
            db.session.commit()

            # Refresh the user_to_update object to get the latest church data
            db.session.refresh(user_to_update)

            # Get updated attendee data to return to frontend
            church_name = "Other"
            if user_to_update.church_id:
                church = Church.query.get(user_to_update.church_id)
                if church:
                    church_name = church.name

            # Construct the user part of the response
            response_user_data = {
                "id": user_to_update.id,
                "name": f"{user_to_update.first_name} {user_to_update.last_name}",
                "email": user_to_update.email,
                "first_name": user_to_update.first_name,
                "last_name": user_to_update.last_name,
                "birthday": (
                    user_to_update.birthday.isoformat()
                    if user_to_update.birthday
                    else None
                ),
                "age": user_to_update.calculate_age(),
                "gender": (
                    user_to_update.gender.value if user_to_update.gender else None
                ),
                "phone": user_to_update.phone,
                "church": church_name,
            }

            return (
                jsonify(
                    {
                        "message": "Waitlist user details updated successfully",
                        "updated_fields": updated_fields,
                        "user": response_user_data,
                    }
                ),
                200,
            )
        else:
            return jsonify({"message": "No fields were updated"}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"Error updating waitlist user {user_id} in event {event_id}: {str(e)}",
            exc_info=True,
        )
        return jsonify({"error": f"Error updating waitlist user: {str(e)}"}), 500


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
