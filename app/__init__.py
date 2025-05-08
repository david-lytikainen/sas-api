from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from limits.strategies import FixedWindowRateLimiter
from dotenv import load_dotenv
import os
from app.extensions import db, migrate, jwt
from datetime import timedelta
import logging

# Load environment variables
load_dotenv()


def create_app():
    app = Flask(__name__)

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)

    # Configure database
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "postgresql://localhost/SAS"
    )
    app.config["LIMITER_DATABASE_URI"] = os.getenv(
        "LIMITER_DATABASE_URL", "postgresql://localhost/SAS"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Configure JWT
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"

    # Implement rate limiting using flask-limiter
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["5 per minute, 10 per hour, 100 per day"],
        storage_uri=os.getenv("LIMITER_DATABASE_URL", "memory://"),
        strategy="fixed-window" 
    )

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # Register blueprints
    from app.routes.user_routes import user_bp
    from app.routes.event_routes import event_bp
    from app.routes.admin_routes import admin_bp
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(event_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api')

    # Set up CORS
    cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5001,*').split(',')
    app.logger.info(f"Initializing CORS with origins: {cors_origins}")
    
    # Use more specific CORS configuration for API 
    CORS(
        app, 
        resources={
            r"/api/*": {"origins": cors_origins},
        },
        supports_credentials=True,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["Content-Type"]
    )
    

    # Handle OPTIONS preflight requests
    @app.route('/<path:path>', methods=['OPTIONS'])
    def handle_options(path):
        return '', 200
        
    # Serve static files (like sounds)
    @app.route('/sounds/<path:filename>')
    def serve_sounds(filename):
        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static/sounds')
        app.logger.info(f"Serving sound file {filename} from {static_dir}")
        return send_from_directory(static_dir, filename)


    return app
