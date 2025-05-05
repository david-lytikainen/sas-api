from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

# Initialize SocketIO with proper configuration
socketio = SocketIO(
    cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    async_mode='threading',
    manage_session=False,
    json=json,  # Use the actual json module
    path='/socket.io/'
)
