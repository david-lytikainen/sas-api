from flask import Blueprint, jsonify, request, make_response
from app.models.event import Event
from app.models.user import User
from app.models.event_attendee import EventAttendee
from app.models.enums import EventStatus, RegistrationStatus
from app.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_cors import cross_origin
from datetime import datetime
from decimal import Decimal
from app.services.event_service import EventService

event_bp = Blueprint('event', __name__)

@event_bp.route('/events', methods=['GET', 'OPTIONS'])
def get_events():
    if request.method == 'OPTIONS':
        return '', 204

    verify_jwt_in_request() 
    user_id = get_jwt_identity()
    return jsonify(EventService.get_events_for_user(user_id))


@event_bp.route('/events', methods=['POST'])
@cross_origin(supports_credentials=True)
@jwt_required()
def create_event():
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        # Only admin and organizer can create events
        if current_user.role_id not in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'description', 'starts_at', 'ends_at', 
                         'address', 'max_capacity', 'price_per_person']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                'error': 'Missing required fields',
                'missing_fields': missing_fields
            }), 400

        # Create new event
        event = Event(
            name=data['name'],
            description=data['description'],
            creator_id=current_user_id,
            starts_at=datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00')),
            ends_at=datetime.fromisoformat(data['ends_at'].replace('Z', '+00:00')),
            address=data['address'],
            max_capacity=data['max_capacity'],
            status=EventStatus.PUBLISHED,
            price_per_person=Decimal(str(data['price_per_person'])),
            registration_deadline=datetime.fromisoformat(data['registration_deadline'].replace('Z', '+00:00')) if 'registration_deadline' in data else None
        )

        db.session.add(event)
        db.session.commit()

        return jsonify(event.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error creating event: {str(e)}")
        return jsonify({'error': 'Failed to create event'}), 500


@event_bp.route('/events/<int:event_id>/register', methods=['POST'])
@jwt_required()
def register_for_event(event_id):
    try:
        current_user_id = get_jwt_identity()
            
        # Check event status
        if event.status != EventStatus.REGISTRATION_OPEN:
            return jsonify({'error': 'Event is not open for registration'}), 400
            
        # Create registration
        registration = EventAttendee(
            event_id=event_id,
            user_id=current_user_id,
            status=RegistrationStatus.REGISTERED
        )
        
        db.session.add(registration)
        db.session.commit()
        
        return jsonify({'message': 'Successfully registered for event'})
    except Exception as e:
        db.session.rollback()
        print(f"Error registering for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to register for event'}), 500

@event_bp.route('/events/<int:event_id>/register', methods=['DELETE'])
@cross_origin(supports_credentials=True)
@jwt_required()
def cancel_registration(event_id):
    try:
        current_user_id = get_jwt_identity()
        registration = EventAttendee.query.filter_by(
            event_id=event_id,
            user_id=current_user_id
        ).first_or_404()
        
        db.session.delete(registration)
        db.session.commit()
        
        return '', 204
    except Exception as e:
        db.session.rollback()
        print(f"Error cancelling registration for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to cancel registration'}), 500

@event_bp.route('/events/<int:event_id>/start', methods=['POST'])
@cross_origin(supports_credentials=True)
@jwt_required()
def start_event(event_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        event = Event.query.get_or_404(event_id)
        
        # Check permissions
        if current_user.role_id not in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
            return jsonify({'error': 'Unauthorized'}), 403
            
        if current_user.role_id == UserRole.ORGANIZER.value and event.creator_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
            
        # Check event status
        if event.status != EventStatus.PUBLISHED:
            return jsonify({'error': 'Event cannot be started'}), 400
            
        # Update event status
        event.status = EventStatus.IN_PROGRESS
        db.session.commit()
        
        return jsonify({'message': 'Event started successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error starting event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to start event'}), 500

@event_bp.route('/events/<int:event_id>/registration-status', methods=['GET'])
@cross_origin(supports_credentials=True)
@jwt_required()
def check_registration_status(event_id):
    try:
        current_user_id = get_jwt_identity()
        registration = EventAttendee.query.filter_by(
            event_id=event_id,
            user_id=current_user_id
        ).first()
        
        return jsonify({'is_registered': bool(registration)})
    except Exception as e:
        print(f"Error checking registration status for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to check registration status'}), 500 