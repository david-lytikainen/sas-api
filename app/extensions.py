from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy()
jwt = JWTManager()
