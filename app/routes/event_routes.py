from flask import Blueprint, request, jsonify

event_bp = Blueprint('event', __name__, url_prefix='/event')

@event_bp.route('/<int:event_id>/start-speed-dating', methods=['POST'])
def start_speed_dating(event_id):
    print(event_id)
        