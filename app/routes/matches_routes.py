from flask import Blueprint, jsonify, request, make_response
from app.models.event_speed_date import EventSpeedDate
from app.models.event import Event
from app.models.user import User
from app.models.event_registration import EventRegistration
from app.extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_cors import cross_origin
from sqlalchemy import and_, or_, exists

matches_bp = Blueprint('matches', __name__)

@matches_bp.route('/matches', methods=['GET', 'OPTIONS'])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_user_matches():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404

        # Get all events where the user is registered AND has matches
        events_with_matches = []
        
        # First get all events where user is registered
        registered_events = db.session.query(Event).join(
            EventRegistration,
            Event.id == EventRegistration.event_id
        ).filter(
            EventRegistration.user_id == current_user_id
        ).all()

        for event in registered_events:
            # Get matches for this event with validation
            matches_query = EventSpeedDate.query.filter(
                and_(
                    EventSpeedDate.event_id == event.id,
                    or_(
                        and_(
                            EventSpeedDate.male_id == current_user_id,
                            EventSpeedDate.male_interested == True,
                            EventSpeedDate.female_interested == True,
                            # Ensure both users exist
                            exists().where(User.id == EventSpeedDate.female_id)
                        ),
                        and_(
                            EventSpeedDate.female_id == current_user_id,
                            EventSpeedDate.male_interested == True,
                            EventSpeedDate.female_interested == True,
                            # Ensure both users exist
                            exists().where(User.id == EventSpeedDate.male_id)
                        )
                    )
                )
            )

            # Execute query and get matches
            matches = matches_query.all()
            
            # Skip if no matches
            if not matches:
                continue

            # Get unique matched users
            unique_matches = set()
            valid_matches = []
            
            for match in matches:
                matched_user_id = match.female_id if match.male_id == current_user_id else match.male_id
                
                # Skip if we've already seen this match
                if matched_user_id in unique_matches:
                    continue
                    
                # Get matched user
                matched_user = User.query.get(matched_user_id)
                if not matched_user:
                    continue
                    
                unique_matches.add(matched_user_id)
                valid_matches.append({
                    'id': str(match.id),
                    'matched_user': {
                        'id': str(matched_user_id),
                        'name': matched_user.name,
                        'table_number': match.table_number,
                        'round_number': match.round_number
                    }
                })

            # Only add event if it has valid matches
            if valid_matches:
                events_with_matches.append({
                    'id': str(event.id),
                    'name': event.name,
                    'date': event.starts_at.strftime('%m/%d/%Y'),
                    'match_count': len(valid_matches),
                    'matches': valid_matches
                })

        return jsonify({
            'success': True,
            'events': events_with_matches
        })

    except Exception as e:
        print(f"Error fetching matches: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred while fetching matches'
        }), 500

@matches_bp.route('/events/<int:event_id>/matches', methods=['GET'])
@cross_origin(supports_credentials=True)
@jwt_required()
def get_event_matches(event_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({'error': 'User not found'}), 404

        # Check if user is registered for this event
        registration = EventRegistration.query.filter_by(
            event_id=event_id,
            user_id=current_user_id
        ).first()
        
        if not registration and current_user.role_id not in [1, 2]:  # Not admin/organizer
            return jsonify({'error': 'Not registered for this event'}), 403

        # Get matches for this event
        matches = EventSpeedDate.query.filter(
            and_(
                EventSpeedDate.event_id == event_id,
                or_(
                    and_(
                        EventSpeedDate.male_id == current_user_id,
                        EventSpeedDate.male_interested == True,
                        EventSpeedDate.female_interested == True
                    ),
                    and_(
                        EventSpeedDate.female_id == current_user_id,
                        EventSpeedDate.male_interested == True,
                        EventSpeedDate.female_interested == True
                    )
                )
            )
        ).all()

        matches_data = []
        for match in matches:
            matched_user_id = match.female_id if match.male_id == current_user_id else match.male_id
            matched_user = User.query.get(matched_user_id)
            if matched_user:
                matches_data.append({
                    'id': str(match.id),
                    'matched_user': {
                        'id': str(matched_user.id),
                        'name': matched_user.name,
                        'table_number': match.table_number,
                        'round_number': match.round_number
                    }
                })

        return jsonify({
            'success': True,
            'matches': matches_data
        })

    except Exception as e:
        print(f"Error fetching event matches: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch matches'
        }), 500 