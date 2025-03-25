from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv
import os
from app.extensions import db, migrate, jwt

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Configure JWT
    app.config['JWT_SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 86400  # 24 hours
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    
    # Simplest possible CORS configuration
    app.config['CORS_HEADERS'] = 'Content-Type'
    CORS(app, origins=['http://localhost:3000', 'http://localhost:3001'], 
         allow_credentials=True, 
         automatic_options=True,
         supports_credentials=True)

    # Add CORS headers to every response
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get('Origin')
        if origin in ['http://localhost:3000', 'http://localhost:3001']:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
        return response
    
    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    # Register blueprints
    from app.routes.user_routes import user_bp
    from app.routes.event_routes import event_bp
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(event_bp, url_prefix='/api')
    
    # Add health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        return {"status": "ok", "message": "API is running"}
    
    # Add stub endpoints for events to prevent 404 errors
    @app.route('/api/events', methods=['GET', 'OPTIONS'])
    def get_events():
        return jsonify([])
    
    @app.route('/api/events/<event_id>', methods=['GET', 'OPTIONS'])
    def get_event(event_id):
        return jsonify({"id": event_id, "name": "Sample Event", "status": "draft"})
    
    @app.route('/api/events/my-events', methods=['GET', 'OPTIONS'])
    def get_my_events():
        return jsonify([])

    return app
    