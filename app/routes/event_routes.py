from flask import Blueprint, jsonify, request
from app.models.event import Event
from app.models.enums import EventStatus
from app import db
from datetime import datetime, timedelta
from decimal import Decimal

event_bp = Blueprint('event', __name__)

@event_bp.route('/events', methods=['GET'])
def get_events():
    try:
        # Try to get events from database
        events = Event.query.all()
        if not events:
            # If no events, return test data
            test_event = Event(
                name="Speed Dating Night",
                description="A fun evening of speed dating!",
                creator_id=1,  # Default admin user
                starts_at=datetime.now() + timedelta(days=7),
                ends_at=datetime.now() + timedelta(days=7, hours=2),
                address="The Dating Lounge, 123 Love Street",
                max_capacity=20,
                status=EventStatus.SCHEDULED,
                price_per_person=Decimal('25.00'),
                registration_deadline=datetime.now() + timedelta(days=6)
            )
            db.session.add(test_event)
            db.session.commit()
            return jsonify([test_event.to_dict()])
        
        return jsonify([event.to_dict() for event in events])
    except Exception as e:
        # Log the error and return a 500 response
        print(f"Error fetching events: {str(e)}")
        return jsonify({'error': 'Failed to fetch events'}), 500

@event_bp.route('/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    try:
        event = Event.query.get_or_404(event_id)
        return jsonify(event.to_dict())
    except Exception as e:
        print(f"Error fetching event {event_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch event'}), 500 