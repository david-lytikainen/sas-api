from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv
import os
from app.extensions import db, migrate, jwt
from datetime import timedelta

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configure CORS - More permissive during development
    CORS(app,
         supports_credentials=True,
         resources={
             r"/api/*": {
                 "origins": ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5001"],
                 "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
                 "allow_headers": ["Content-Type", "Authorization", "Accept", "X-Requested-With"],
                 "expose_headers": ["Authorization", "Content-Type"],
                 "max_age": 3600,
                 "supports_credentials": True
             }
         })

    # Add CORS headers to all responses
    @app.after_request
    def after_request(response):
        origin = request.headers.get('Origin')
        if origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
            response.headers.add('Access-Control-Allow-Origin', origin)
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept,X-Requested-With')
            response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS,PATCH')
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            response.headers.add('Access-Control-Expose-Headers', 'Authorization,Content-Type')
        return response

    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://localhost/SAS')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Configure JWT
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    
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
    @app.route('/api/health', methods=['GET'])
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
    