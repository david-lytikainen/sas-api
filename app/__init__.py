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
    
    # Configure CORS
    CORS(app,
     supports_credentials=True,
     resources={
         r"/api/*": {
             "origins": "http://localhost:3000",
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"]
         }
     })


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
    from app.routes.matches_routes import matches_bp
    app.register_blueprint(user_bp, url_prefix='/api/user')
    app.register_blueprint(event_bp, url_prefix='/api')
    app.register_blueprint(matches_bp, url_prefix='/api')
    
    @app.after_request
    def log_response_headers(response):
        print("Response headers")
        for header, value in response.headers.items():
            print(f"{header}: {value}")
        return response

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
    