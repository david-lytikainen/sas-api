from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
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
    
    # Initialize Flask extensions
    db.init_app(app) # initialize sqlalchemy
    migrate.init_app(app, db) # initialize flask-migrate

    return app
    