from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from app import models  # noqa: F401
from app.extensions import db, migrate
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'super-secret')  # Change this in production!
    
    # Initialize Flask extensions
    CORS(app)  # Enable CORS for all routes
    db.init_app(app)  # initialize sqlalchemy
    migrate.init_app(app, db)  # initialize flask-migrate
    JWTManager(app)  # initialize JWT

    # Register blueprints
    from app.routes.user_routes import user_bp
    app.register_blueprint(user_bp, url_prefix='/api')

    return app
    