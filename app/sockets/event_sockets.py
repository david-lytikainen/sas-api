from app.extensions import socketio, logger
from flask_socketio import emit, join_room, leave_room
from app.services.event_timer_service import EventTimerService
from flask_jwt_extended import decode_token
from flask import request, current_app
import json

# Explicitly define the namespace for all handlers
NAMESPACE = '/'

@socketio.on('connect')
def handle_connect():
    """Handle client connection with various token authentication methods."""
    try:
        # Log connection attempt
        logger.info(f"Socket connection attempt - request details: {request.sid}")
        
        # Debug request parameters
        if hasattr(request, 'args'):
            logger.info(f"Socket connection request args: {request.args}")
        
        if hasattr(request, 'headers'):
            logger.info(f"Socket connection request headers: {request.headers}")
        
        # Extract token from various sources
        token = None
        
        # Check for auth parameter in different formats
        auth = None
        if hasattr(request, 'args') and 'auth' in request.args:
            auth = request.args.get('auth')
            logger.info(f"Found auth parameter: {auth}")
        
        # Handle auth as object with token field
        if auth:
            try:
                if isinstance(auth, dict) and 'token' in auth:
                    token = auth['token']
                    logger.info("Found token in auth object")
                else:
                    # Try to parse it as JSON if it's a string
                    try:
                        auth_obj = json.loads(auth)
                        if isinstance(auth_obj, dict) and 'token' in auth_obj:
                            token = auth_obj['token']
                            logger.info("Found token in parsed auth JSON")
                        else:
                            # Use auth directly as token
                            token = auth
                            logger.info("Using auth parameter directly as token")
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, use auth directly as token
                        token = auth
                        logger.info("Using auth parameter directly as token (parse failed)")
            except Exception as e:
                logger.error(f"Error extracting token from auth: {e}")
                
        # Check query parameters
        if not token and hasattr(request, 'args') and 'token' in request.args:
            token = request.args.get('token')
            logger.info("Found token in query parameters")
                
        # Check headers
        if not token and hasattr(request, 'headers') and request.headers.get('Authorization'):
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                logger.info("Found token in Authorization header")
        
        if not token:
            logger.error("Socket connection rejected: No token found in any location")
            return False  # Reject the connection
        
        try:
            # Verify token
            decode_token(token)
            logger.info(f"Socket connection accepted for {request.sid}: Valid JWT token")
            return True  # Accept the connection
        except Exception as e:
            logger.error(f"Socket connection rejected: Invalid token: {str(e)}")
            return False  # Reject the connection
            
    except Exception as e:
        logger.error(f"Socket connection error: {str(e)}")
        return False  # Reject on any error

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