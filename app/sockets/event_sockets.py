from app.extensions import socketio
from flask_socketio import emit, join_room, leave_room
from app.services.event_timer_service import EventTimerService
from flask_jwt_extended import decode_token
from flask import request, current_app
import json
import logging

logger = logging.getLogger(__name__)

@socketio.on('connect')
def handle_connect(auth):
    """Handle client connection with token authentication from auth payload."""
    logger.info("Socket connection attempt with auth: %s", auth)
    
    if not auth or 'token' not in auth:
        logger.error("Socket connection rejected: No token provided in auth payload.")
        return False # Reject the connection
    
    token = auth['token']
    try:
        # Verify the token is valid
        decode_token(token)
        logger.info("Socket connection accepted: Valid JWT token from auth.")
        return True  # Accept the connection
    except Exception as e:
        logger.error(f"Socket connection rejected due to invalid token in auth: {str(e)}")
        return False  # Reject the connection

@socketio.on('join')
def handle_join(data):
    """Handle client joining an event room"""
    logger.info("Socket 'join' event received with data: %s", data)
    if 'event_id' not in data:
        logger.error("Socket 'join' event rejected: Missing event_id")
        emit('error', {'message': 'event_id is required'})
        return
    
    event_id = data['event_id']
    room = f"event_{event_id}"
    join_room(room)
    logger.info(f"Client joined room: {room}")
    
    # Send initial timer status
    timer_status = EventTimerService.get_timer_status(event_id)
    logger.info(f"Emitting initial timer_update to room {room}: {timer_status}")
    emit('timer_update', timer_status, room=room)

@socketio.on('leave')
def handle_leave(data):
    """Handle client leaving an event room"""
    logger.info("Socket 'leave' event received with data: %s", data)
    if 'event_id' not in data:
        logger.error("Socket 'leave' event ignored: Missing event_id")
        return
    
    event_id = data['event_id']
    room = f"event_{event_id}"
    leave_room(room)
    logger.info(f"Client left room: {room}")

@socketio.on('timer_start')
def handle_timer_start(data):
    """Handle starting a timer round"""
    logger.info("Socket 'timer_start' event received with data: %s", data)
    if 'event_id' not in data:
        logger.error("Socket 'timer_start' event rejected: Missing event_id")
        emit('error', {'message': 'event_id is required'})
        return
    
    event_id = data['event_id']
    round_number = data.get('round_number')
    
    result = EventTimerService.start_round(event_id, round_number)
    room = f"event_{event_id}"
    
    logger.info(f"Emitting timer_update for timer_start to room {room}: {result}")
    emit('timer_update', result, room=room)

@socketio.on('timer_pause')
def handle_timer_pause(data):
    """Handle pausing a timer round"""
    logger.info("Socket 'timer_pause' event received with data: %s", data)
    if 'event_id' not in data or 'time_remaining' not in data:
        logger.error("Socket 'timer_pause' event rejected: Missing event_id or time_remaining")
        emit('error', {'message': 'event_id and time_remaining are required'})
        return
    
    event_id = data['event_id']
    time_remaining = data['time_remaining']
    
    result = EventTimerService.pause_round(event_id, time_remaining)
    room = f"event_{event_id}"
    
    logger.info(f"Emitting timer_update for timer_pause to room {room}: {result}")
    emit('timer_update', result, room=room)

@socketio.on('timer_resume')
def handle_timer_resume(data):
    """Handle resuming a timer round"""
    logger.info("Socket 'timer_resume' event received with data: %s", data)
    if 'event_id' not in data:
        logger.error("Socket 'timer_resume' event rejected: Missing event_id")
        emit('error', {'message': 'event_id is required'})
        return
    
    event_id = data['event_id']
    
    result = EventTimerService.resume_round(event_id)
    room = f"event_{event_id}"
    
    logger.info(f"Emitting timer_update for timer_resume to room {room}: {result}")
    emit('timer_update', result, room=room)

@socketio.on('timer_next')
def handle_timer_next(data):
    """Handle advancing to the next round"""
    logger.info("Socket 'timer_next' event received with data: %s", data)
    if 'event_id' not in data:
        logger.error("Socket 'timer_next' event rejected: Missing event_id")
        emit('error', {'message': 'event_id is required'})
        return
    
    event_id = data['event_id']
    max_rounds = data.get('max_rounds', 10)
    
    result = EventTimerService.next_round(event_id, max_rounds)
    room = f"event_{event_id}"
    
    logger.info(f"Emitting timer_update for timer_next to room {room}: {result}")
    emit('timer_update', result, room=room)

@socketio.on('timer_update_duration')
def handle_update_duration(data):
    """Handle updating the round duration"""
    logger.info("Socket 'timer_update_duration' event received with data: %s", data)
    if 'event_id' not in data or 'round_duration' not in data:
        logger.error("Socket 'timer_update_duration' event rejected: Missing event_id or round_duration")
        emit('error', {'message': 'event_id and round_duration are required'})
        return
    
    event_id = data['event_id']
    round_duration = data['round_duration']
    
    result = EventTimerService.update_duration(event_id, round_duration)
    room = f"event_{event_id}"
    
    logger.info(f"Emitting timer_update for timer_update_duration to room {room}: {result}")
    emit('timer_update', result, room=room) 