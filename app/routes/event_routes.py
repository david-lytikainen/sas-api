from flask import Blueprint, jsonify, request, make_response
from app.models.event import Event
from app.models.user import User
from app.models.event_registration import EventRegistration
from app.models.enums import EventStatus, UserRole, RegistrationStatus
from app.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_cors import cross_origin
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_

event_bp = Blueprint('event', __name__)

@event_bp.route('/events', methods=['GET', 'OPTIONS'])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_events():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        # Get query parameters for filtering
        status = request.args.get('status')
        
        # Base query
        query = Event.query

        # Apply filters
        if status:
            query = query.filter(Event.status == status)
        
        # Get all events
        events = query.all()
        
        # Format response
        events_data = []
        for event in events:
            event_data = event.to_dict()
            # Add registration status for attendees
            if current_user.role_id == UserRole.ATTENDEE.value:
                registration = EventRegistration.query.filter_by(
                    event_id=event.id,
                    user_id=current_user_id
                ).first()
                event_data['is_registered'] = bool(registration)
            events_data.append(event_data)

        return jsonify(events_data)
    except Exception as e:
        print(f"Error fetching events: {str(e)}")
        return jsonify({'error': 'Failed to fetch events'}), 500

@event_bp.route('/events/my-events', methods=['GET'])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_my_events():
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        # For admin/organizer: get events they created
        # For attendee: get events they're registered for
        if current_user.role_id in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
            events = Event.query.filter_by(creator_id=current_user_id).all()
        else:
            events = Event.query.join(EventRegistration).filter(
                EventRegistration.user_id == current_user_id
            ).all()

        return jsonify([event.to_dict() for event in events])
    except Exception as e:
        print(f"Error fetching my events: {str(e)}")
        return jsonify({'error': 'Failed to fetch events'}), 500

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

@event_bp.route('/events/<int:event_id>', methods=['GET'])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_event(event_id):
    try:
        current_user_id = get_jwt_identity()
        event = Event.query.get_or_404(event_id)
        
        event_data = event.to_dict()
        
        # Add registration status for attendees
        current_user = User.query.get(current_user_id)
        if current_user.role_id == UserRole.ATTENDEE.value:
            registration = EventRegistration.query.filter_by(
                event_id=event_id,
                user_id=current_user_id
            ).first()
            event_data['is_registered'] = bool(registration)
            
        return jsonify(event_data)
    except Exception as e:
        print(f"Error fetching event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch event'}), 500

@event_bp.route('/events/<int:event_id>', methods=['PUT'])
@cross_origin(supports_credentials=True)
@jwt_required()
def update_event(event_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        event = Event.query.get_or_404(event_id)
        
        # Check permissions
        if current_user.role_id not in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if current_user.role_id == UserRole.ORGANIZER.value and event.creator_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json()
        
        # Update fields
        for field in ['name', 'description', 'starts_at', 'ends_at', 'address', 
                     'max_capacity', 'price_per_person', 'registration_deadline']:
            if field in data:
                if field in ['starts_at', 'ends_at', 'registration_deadline']:
                    value = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                elif field == 'price_per_person':
                    value = Decimal(str(data[field]))
                else:
                    value = data[field]
                setattr(event, field, value)

        db.session.commit()
        return jsonify(event.to_dict())
    except Exception as e:
        db.session.rollback()
        print(f"Error updating event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to update event'}), 500

@event_bp.route('/events/<int:event_id>', methods=['DELETE'])
@cross_origin(supports_credentials=True)
@jwt_required()
def delete_event(event_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        event = Event.query.get_or_404(event_id)
        
        # Check permissions
        if current_user.role_id not in [UserRole.ADMIN.value, UserRole.ORGANIZER.value]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if current_user.role_id == UserRole.ORGANIZER.value and event.creator_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403

        db.session.delete(event)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete event'}), 500

@event_bp.route('/events/<int:event_id>/register', methods=['POST'])
@cross_origin(supports_credentials=True)
@jwt_required()
def register_for_event(event_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        event = Event.query.get_or_404(event_id)
        
        # Check if user is an attendee
        if current_user.role_id != UserRole.ATTENDEE.value:
            return jsonify({'error': 'Only attendees can register for events'}), 403
            
        # Check if already registered
        existing_registration = EventRegistration.query.filter_by(
            event_id=event_id,
            user_id=current_user_id
        ).first()
        
        if existing_registration:
            return jsonify({'error': 'Already registered for this event'}), 400
            
        # Check event status
        if event.status != EventStatus.PUBLISHED:
            return jsonify({'error': 'Event is not open for registration'}), 400
            
        # Create registration
        registration = EventRegistration(
            event_id=event_id,
            user_id=current_user_id
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
        registration = EventRegistration.query.filter_by(
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
        registration = EventRegistration.query.filter_by(
            event_id=event_id,
            user_id=current_user_id
        ).first()
        
        return jsonify({'is_registered': bool(registration)})
    except Exception as e:
        print(f"Error checking registration status for event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to check registration status'}), 500 