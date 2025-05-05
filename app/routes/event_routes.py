from flask import Blueprint, jsonify, request, Response, stream_with_context
from app.models.event import Event
from app.models.user import User
from app.models.event_attendee import EventAttendee
from app.models.enums import EventStatus, RegistrationStatus, UserRole, Gender
from app.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_cors import cross_origin
from app.exceptions import UnauthorizedError, MissingFieldsError
from app.services.event_service import EventService
from app.services.speed_date_service import SpeedDateService
from app.services.event_timer_service import EventTimerService
from datetime import datetime
from flask import current_app

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
    registrations_data = [
        {
            "event_id": reg.event_id, 
            "status": reg.status.value,
            "pin": reg.pin,
            "registration_date": reg.registration_date.isoformat() if reg.registration_date else None,
            "check_in_date": reg.check_in_date.isoformat() if reg.check_in_date else None
        } 
        for reg in user_registrations
    ]
    
    # Return both events and registrations
    return jsonify({
        "events": events_data,
        "registrations": registrations_data
    })


@event_bp.route('/events/<int:event_id>', methods=['GET', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def get_event_by_id(event_id):
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        verify_jwt_in_request() 
        user_id = get_jwt_identity()
        
        # Get the specific event
        event = Event.query.get_or_404(event_id)
        event_data = event.to_dict()
        
        # Check if user is registered for this event
        registration = EventAttendee.query.filter_by(user_id=user_id, event_id=event_id).first()
        
        if registration:
            registration_data = {
                "status": registration.status.value,
                "pin": registration.pin,
                "registration_date": registration.registration_date.isoformat() if registration.registration_date else None,
                "check_in_date": registration.check_in_date.isoformat() if registration.check_in_date else None
            }
            event_data["registration"] = registration_data
        
        return jsonify(event_data)
    except Exception as e:
        print(f"Error fetching event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch event details'}), 500


@event_bp.route('/events/create', methods=['POST'])
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
    response, status_code = EventService.cancel_registration(event_id, user_id)
    return jsonify(response), status_code


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

        # Check event status - using .value since status is now a string
        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return jsonify({'error': 'Event cannot be started'}), 400
            
        # Update event status - using .value since status is now a string
        event.status = EventStatus.IN_PROGRESS.value
        db.session.commit()
        
        # Generate speed dating schedule
        schedule_success = SpeedDateService.generate_schedule(event_id)
        
        if schedule_success:
            return jsonify({'message': 'Event started successfully and schedule generated'})
        else:
            # If schedule generation fails, log but still return success for starting the event
            print(f"Warning: Event {event_id} started but schedule generation failed")
            return jsonify({'message': 'Event started successfully but schedule could not be generated. Please generate it manually.'})
    except Exception as e:
        db.session.rollback()
        print(f"Error starting event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to start event'}), 500

@event_bp.route('/events/<int:event_id>/check-in', methods=['POST'])
@jwt_required()
def check_in(event_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or 'pin' not in data:
        return jsonify({'error': 'Missing PIN'}), 400
        
    pin = data['pin']
    
    response, status_code = EventService.check_in(event_id, current_user_id, pin)
    return jsonify(response), status_code

@event_bp.route('/events/<int:event_id>/status', methods=['PATCH', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def update_event_status(event_id):
    if request.method == 'OPTIONS':
        return '', 204
        
    verify_jwt_in_request()
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate the request
    if not data or 'status' not in data:
        return jsonify({'error': 'Missing status'}), 400
        
    status = data['status']
    
    try:
        # Validate status values
        valid_statuses = [status.value for status in EventStatus]
        if status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        
        # Get the event
        event = Event.query.get_or_404(event_id)
        
        # Get the user with role preloaded to avoid lazy loading issues
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        # Check if user has permission to update the event
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to update this event'}), 403
        
        # Now we can directly assign the status string
        event.status = status
        db.session.commit()
        
        return jsonify({'message': 'Event status updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_event_status: {str(e)}")
        return jsonify({'error': f'Error updating status: {str(e)}'}), 500

@event_bp.route('/events/<int:event_id>/attendee-pins', methods=['GET', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def get_event_attendee_pins(event_id):
    if request.method == 'OPTIONS':
        return '', 204
        
    verify_jwt_in_request()
    current_user_id = get_jwt_identity()
    
    try:
        # Get the event
        event = Event.query.get_or_404(event_id)
        
        # Get the user with role preloaded to avoid lazy loading issues
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        # Check if user has permission to view pins
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to view attendee pins'}), 403
        
        # Get all attendees with their pins
        attendees = db.session.query(
            EventAttendee, User
        ).join(
            User, EventAttendee.user_id == User.id
        ).filter(
            EventAttendee.event_id == event_id,
            EventAttendee.status.in_([RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN])
        ).all()
        
        attendee_data = [
            {
                'name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'pin': attendee.pin,
                'status': attendee.status.value
            }
            for attendee, user in attendees
        ]
        
        return jsonify(attendee_data), 200
    except Exception as e:
        print(f"Error in get_event_attendee_pins: {str(e)}")
        return jsonify({'error': f'Error retrieving pins: {str(e)}'}), 500

@event_bp.route('/events/<int:event_id>/attendees', methods=['GET', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def get_event_attendees(event_id):
    if request.method == 'OPTIONS':
        return '', 204
        
    verify_jwt_in_request()
    current_user_id = get_jwt_identity()
    
    try:
        # Get the event
        event = Event.query.get_or_404(event_id)
        
        # Get the user with role preloaded to avoid lazy loading issues
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        # Check if user has permission to view attendees
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to view attendee information'}), 403
        
        # Get all attendees with detailed user information
        attendees = db.session.query(
            EventAttendee, User
        ).join(
            User, EventAttendee.user_id == User.id
        ).filter(
            EventAttendee.event_id == event_id,
            EventAttendee.status.in_([RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN])
        ).all()
        
        attendee_data = [
            {
                'id': user.id,
                'name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'birthday': user.birthday.isoformat() if user.birthday else None,
                'age': user.calculate_age(),
                'gender': user.gender.value if user.gender else None,
                'phone': user.phone,
                'registration_date': attendee.registration_date.isoformat() if attendee.registration_date else None,
                'check_in_date': attendee.check_in_date.isoformat() if attendee.check_in_date else None,
                'status': attendee.status.value,
                'pin': attendee.pin
            }
            for attendee, user in attendees
        ]
        
        return jsonify(attendee_data), 200
    except Exception as e:
        print(f"Error in get_event_attendees: {str(e)}")
        return jsonify({'error': f'Error retrieving attendees: {str(e)}'}), 500

@event_bp.route('/events/<int:event_id>/attendees/<int:attendee_id>', methods=['PATCH', 'OPTIONS'])
@cross_origin(supports_credentials=True)
def update_attendee_details(event_id, attendee_id):
    if request.method == 'OPTIONS':
        return '', 204
        
    verify_jwt_in_request()
    current_user_id = get_jwt_identity()
    
    try:
        # Get the event
        event = Event.query.get_or_404(event_id)
        
        # Get the user and verify permissions
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        # Check if user has permission to update attendees
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to update attendee information'}), 403
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No update data provided'}), 400
        
        # Get the user to update
        user_to_update = User.query.get_or_404(attendee_id)
        
        # Also verify this user is actually registered for this event
        attendee = EventAttendee.query.filter_by(event_id=event_id, user_id=attendee_id).first()
        if not attendee:
            return jsonify({'error': 'User is not registered for this event'}), 404
        
        # Track which fields were updated
        updated_fields = []
        
        # Update user fields if provided
        if 'first_name' in data and data['first_name']:
            user_to_update.first_name = data['first_name']
            updated_fields.append('first_name')
            
        if 'last_name' in data and data['last_name']:
            user_to_update.last_name = data['last_name']
            updated_fields.append('last_name')
            
        if 'email' in data and data['email']:
            user_to_update.email = data['email']
            updated_fields.append('email')
            
        if 'phone' in data and data['phone']:
            user_to_update.phone = data['phone']
            updated_fields.append('phone')
            
        if 'gender' in data and data['gender']:
            try:
                user_to_update.gender = Gender[data['gender'].upper()]
                updated_fields.append('gender')
            except KeyError:
                return jsonify({'error': 'Invalid gender value. Must be either MALE or FEMALE'}), 400
                
        if 'birthday' in data and data['birthday']:
            try:
                user_to_update.birthday = datetime.strptime(data['birthday'], '%Y-%m-%d').date()
                updated_fields.append('birthday')
            except ValueError:
                return jsonify({'error': 'Invalid birthday format. Use YYYY-MM-DD'}), 400
        
        # Update attendee fields
        if 'pin' in data and data['pin']:
            attendee.pin = data['pin']
            updated_fields.append('pin')
        
        # Save changes if any fields were updated
        if updated_fields:
            db.session.commit()
            return jsonify({
                'message': 'Attendee details updated successfully',
                'updated_fields': updated_fields
            }), 200
        else:
            return jsonify({'message': 'No fields were updated'}), 200
            
    except Exception as e:
        db.session.rollback()
        print(f"Error updating attendee details: {str(e)}")
        return jsonify({'error': f'Error updating attendee: {str(e)}'}), 500

@event_bp.route('/events/<int:event_id>/schedule', methods=['GET'])
@jwt_required()
def get_schedule(event_id):
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        # Check if event is in progress, paused, or completed
        if event.status not in [EventStatus.IN_PROGRESS.value, EventStatus.COMPLETED.value, EventStatus.PAUSED.value]:
            return jsonify({'error': 'Schedule not available. Event has not started'}), 400
            
        # Check if user is registered for this event
        attendee = EventAttendee.query.filter_by(
            event_id=event_id,
            user_id=current_user_id
        ).first()
        
        if not attendee:
            return jsonify({'error': 'You are not registered for this event'}), 403
            
        # Get the user's schedule
        schedule = SpeedDateService.get_schedule_for_attendee(event_id, current_user_id)
        
        if not schedule:
            return jsonify({'message': 'No schedule available. Make sure you are checked in.'}), 404
            
        return jsonify({'schedule': schedule}), 200
        
    except Exception as e:
        print(f"Error retrieving schedule for event {event_id}, user {current_user_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve schedule'}), 500

@event_bp.route('/events/<int:event_id>/all-schedules', methods=['GET'])
@jwt_required()
def get_all_schedules(event_id):
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        # Check permissions
        current_user = User.query.get(current_user_id)
        if current_user.role_id not in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
            return jsonify({'error': 'Unauthorized'}), 403
            
        if current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) != str(current_user_id):
            return jsonify({'error': 'Unauthorized'}), 403
        
        # --- Add Logging --- 
        current_app.logger.info(f"Checking status for event {event_id}. Current status in DB: {event.status}")
        # -------------------
        
        # Check if event is in progress, paused, or completed
        if event.status not in [EventStatus.IN_PROGRESS.value, EventStatus.COMPLETED.value, EventStatus.PAUSED.value]:
            current_app.logger.warning(f"Event {event_id} status '{event.status}' is not valid for viewing schedules. Returning 400.") # Log why it fails
            return jsonify({'error': 'Schedule not available. Event has not started'}), 400
            
        # Get all schedules
        schedules = SpeedDateService.get_all_schedules(event_id)
        
        return jsonify({'schedules': schedules}), 200
        
    except Exception as e:
        print(f"Error retrieving all schedules for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve schedules'}), 500


@event_bp.route('/events/<int:event_id>/timer', methods=['GET'])
@jwt_required()
def get_timer_status(event_id):
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        # Check if user is admin or event creator
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        try:
            # Try to get timer status
            timer_status = EventTimerService.get_timer_status(event_id)
            
            # If user is not admin/organizer, return limited data to reduce payload size
            if not is_admin and not is_event_creator:
                limited_status = {
                    'has_timer': timer_status.get('has_timer', False),
                    'status': timer_status.get('status'),
                    'current_round': timer_status.get('timer', {}).get('current_round') if timer_status.get('timer') else None,
                    'message': timer_status.get('message')
                }
                return jsonify(limited_status), 200
            
            # Return full timer data for admins/organizers
            return jsonify(timer_status), 200
            
        except Exception as timer_error:
            # Log the detailed error
            print(f"Error in timer service: {str(timer_error)}")
            
            # Return a graceful error response that won't crash the frontend
            if not is_admin and not is_event_creator:
                return jsonify({
                    'has_timer': False,
                    'status': 'unknown',
                    'current_round': None,
                    'message': 'Timer temporarily unavailable'
                }), 200
            else:
                return jsonify({
                    'has_timer': False,
                    'status': 'error',
                    'message': 'Timer service error. Please try again later.',
                    'debug_info': str(timer_error) if is_admin else None
                }), 200
        
    except Exception as e:
        print(f"Error retrieving timer status for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve timer status'}), 500


@event_bp.route('/events/<int:event_id>/timer/initialize', methods=['POST'])
@jwt_required()
def initialize_timer(event_id):
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        # Verify user is admin or event creator
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to manage event timer'}), 403
        
        # Get round duration from request, default to 3 minutes (180 seconds)
        data = request.get_json() or {}
        round_duration = data.get('round_duration', 180)
        
        # Initialize timer
        timer_dict = EventTimerService.initialize_timer(event_id, round_duration)
        
        # --- Broadcast Update ---
        EventTimerService.broadcast_timer_update(event_id)
        # ----------------------
        
        return jsonify({
            'message': 'Timer initialized',
            'timer': timer_dict
        }), 200
        
    except Exception as e:
        print(f"Error initializing timer for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to initialize timer'}), 500


@event_bp.route('/events/<int:event_id>/timer/start', methods=['POST'])
@jwt_required()
def start_round(event_id):
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        # Verify user is admin or event creator
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to manage event timer'}), 403
        
        # Get round number from request if provided
        data = request.get_json() or {}
        round_number = data.get('round_number')
        
        # Start the round
        result = EventTimerService.start_round(event_id, round_number)
        
        if 'error' in result:
            return jsonify(result), 400
            
        # --- Broadcast Update ---
        EventTimerService.broadcast_timer_update(event_id)
        # ----------------------
            
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error starting round for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to start round'}), 500


@event_bp.route('/events/<int:event_id>/timer/pause', methods=['POST'])
@jwt_required()
def pause_round(event_id):
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        # Verify user is admin or event creator
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to manage event timer'}), 403
        
        # Get time remaining from request
        data = request.get_json() or {}
        if 'time_remaining' not in data:
            return jsonify({'error': 'time_remaining is required'}), 400
            
        time_remaining = data.get('time_remaining')
        
        # --- REVERTED: Only handle manual pause requests --- 
        # Client now handles the transition to 'between_rounds' locally
        result = EventTimerService.pause_round(event_id, time_remaining)
        print(f"Event {event_id}: Pausing round with {time_remaining}s left.")
        # ------------------------------------------------------
        
        if 'error' in result:
            return jsonify(result), 400
            
        # --- Broadcast Update ---
        EventTimerService.broadcast_timer_update(event_id)
        # ----------------------
            
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error pausing round for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to pause round'}), 500


@event_bp.route('/events/<int:event_id>/timer/resume', methods=['POST'])
@jwt_required()
def resume_round(event_id):
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        # Verify user is admin or event creator
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to manage event timer'}), 403
        
        # Resume the round
        result = EventTimerService.resume_round(event_id)
        
        if 'error' in result:
            return jsonify(result), 400
            
        # --- Broadcast Update ---
        EventTimerService.broadcast_timer_update(event_id)
        # ----------------------
            
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error resuming round for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to resume round'}), 500


@event_bp.route('/events/<int:event_id>/timer/next', methods=['POST'])
@jwt_required()
def next_round(event_id):
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        # Verify user is admin or event creator
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to manage event timer'}), 403
        
        # Get max rounds from request if provided
        data = request.get_json() or {}
        max_rounds = data.get('max_rounds', 10)
        
        # Advance to next round
        result = EventTimerService.next_round(event_id, max_rounds)
        
        if 'error' in result:
            return jsonify(result), 400
            
        # --- Broadcast Update ---
        EventTimerService.broadcast_timer_update(event_id)
        # ----------------------
            
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error advancing to next round for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to advance to next round'}), 500


@event_bp.route('/events/<int:event_id>/timer/duration', methods=['PUT'])
@jwt_required()
def update_round_duration(event_id):
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        # Verify user is admin or event creator
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 403
            
        is_admin = current_user.role_id == UserRole.ADMIN.value
        is_event_creator = current_user.role_id == UserRole.ORGANIZER.value and str(event.creator_id) == str(current_user_id)
        
        if not is_admin and not is_event_creator:
            return jsonify({'error': 'Unauthorized to manage event timer'}), 403
        
        # Get round duration from request
        data = request.get_json() or {}
        if 'round_duration' not in data:
            return jsonify({'error': 'round_duration is required'}), 400
            
        round_duration = data.get('round_duration')
        
        # Update round duration
        result = EventTimerService.update_duration(event_id, round_duration)
        
        if 'error' in result:
            return jsonify(result), 400
            
        # --- Broadcast Update ---
        EventTimerService.broadcast_timer_update(event_id)
        # ----------------------
            
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error updating round duration for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to update round duration'}), 500

@event_bp.route('/events/<int:event_id>/round-info', methods=['GET'])
@jwt_required()
def get_round_info(event_id):
    """Get minimal round information for regular attendees"""
    current_user_id = get_jwt_identity()
    
    try:
        # Check if event exists
        event = Event.query.get_or_404(event_id)
        
        try:
            # Try to get timer status
            timer_status = EventTimerService.get_timer_status(event_id)
            
            # Return only round information
            round_info = {
                'has_timer': timer_status.get('has_timer', False),
                'status': timer_status.get('status'),
                'current_round': timer_status.get('timer', {}).get('current_round') if timer_status.get('timer') else None
            }
            
            return jsonify(round_info), 200
            
        except Exception as timer_error:
            # Fallback if timer service fails
            print(f"Error in timer service for round info: {str(timer_error)}")
            return jsonify({
                'has_timer': False,
                'status': 'unknown',
                'current_round': None,
                'error': 'Timer temporarily unavailable'
            }), 200
        
    except Exception as e:
        print(f"Error retrieving round info for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve round information'}), 500

@event_bp.route('/events/<int:event_id>/sse', methods=['GET'])
def handle_sse_requests(event_id):
    """
    This endpoint exists only to catch SSE connection attempts from clients
    and return a proper 404 rather than a 405 Method Not Allowed error.
    """
    current_app.logger.warning(f"Attempted SSE connection to non-existent endpoint for event {event_id}")
    return jsonify({
        "error": "Server-Sent Events are not supported",
        "message": "This endpoint has been deprecated. Please use standard polling."
    }), 404
