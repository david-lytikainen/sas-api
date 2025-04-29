from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
from app.extensions import db, migrate, jwt, socketio
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
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Configure JWT
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"

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
    CORS(
        app, 
        resources={r"/api/*": {"origins": cors_origins}},
        supports_credentials=True,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"]
    )
    
    # Set cors allowed origins as app config
    app.config['SOCKETIO_CORS_ALLOWED_ORIGINS'] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5001", "*"]
    
    # Initialize SocketIO with more explicit configuration
    socketio.init_app(
        app, 
        cors_allowed_origins=app.config['SOCKETIO_CORS_ALLOWED_ORIGINS'],
        logger=True,
        engineio_logger=True,
        ping_timeout=60,
        ping_interval=25,
        async_mode='threading'
    )
    
    app.logger.info("SocketIO initialized with CORS origins: %s", app.config['SOCKETIO_CORS_ALLOWED_ORIGINS'])

    # Import socket event handlers
    from app.sockets import event_sockets
    app.logger.info("Socket event handlers registered")

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
