from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.extensions import db, migrate, jwt
from app.utils.email import mail
from datetime import timedelta
import logging

# Load environment variables
load_dotenv()


def create_app():
    app = Flask(__name__)

    # Set testing mode from environment variable
    app.config["TESTING"] = os.getenv("FLASK_ENV") in ["development", "testing"]

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)

    # Configure database
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "postgresql://localhost/SAS"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["LIMITER_DATABASE_URI"] = os.getenv(
        "LIMITER_DATABASE_URL", "postgresql://localhost/SAS"
    )

    # Configure JWT
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"

    # Email configuration
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() in [
        "true",
        "1",
        "t",
    ]
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["CLIENT_URL"] = os.getenv("CLIENT_URL", "http://localhost:3000")
    app.config["STRIPE_SECRET_KEY"] = os.getenv("STRIPE_SECRET_KEY", "")
    app.config["STRIPE_WEBHOOK_SECRET"] = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    app.config["STRIPE_CONNECT_COUNTRY"] = os.getenv(
        "STRIPE_CONNECT_COUNTRY", "US"
    )  # TODO: change if platform country differs
    app.config["STRIPE_CONNECT_REFRESH_URL"] = os.getenv(
        "STRIPE_CONNECT_REFRESH_URL",
        f'{app.config["CLIENT_URL"]}/events?view=create&stripe_connect=refresh',
    )  # TODO: replace with final Stripe refresh URL if needed
    app.config["STRIPE_CONNECT_RETURN_URL"] = os.getenv(
        "STRIPE_CONNECT_RETURN_URL",
        f'{app.config["CLIENT_URL"]}/events?view=create&stripe_connect=return',
    )  # TODO: replace with final Stripe return URL if needed
    app.config["STRIPE_CHECKOUT_SUCCESS_URL"] = os.getenv(
        "STRIPE_CHECKOUT_SUCCESS_URL",
        f'{app.config["CLIENT_URL"]}/events?view=create&checkout=success&session_id={{CHECKOUT_SESSION_ID}}',
    )  # TODO: replace with final Stripe success URL if needed
    app.config["STRIPE_CHECKOUT_CANCEL_URL"] = os.getenv(
        "STRIPE_CHECKOUT_CANCEL_URL",
        f'{app.config["CLIENT_URL"]}/events?view=create&checkout=cancelled',
    )  # TODO: replace with final Stripe cancel URL if needed

    # Implement rate limiting using flask-limiter
    Limiter(
        get_remote_address,
        app=app,
        default_limits=["150 per minute, 10000 per hour, 100000 per day"],
        storage_uri=os.getenv("LIMITER_DATABASE_URL", "memory://"),
        strategy="fixed-window",
    )

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)

    # Register blueprints
    from app.routes.user_routes import user_bp
    from app.routes.event_routes import event_bp
    from app.routes.admin_routes import admin_bp

    app.register_blueprint(user_bp, url_prefix="/api/user")
    app.register_blueprint(event_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api")

    # Set up CORS
    cors_origins = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5001,*",
    ).split(",")
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
        expose_headers=["Content-Type"],
    )

    # Handle OPTIONS preflight requests
    @app.route("/<path:path>", methods=["OPTIONS"])
    def handle_options(path):
        return "", 200

    # Serve static files (like sounds)
    @app.route("/sounds/<path:filename>")
    def serve_sounds(filename):
        static_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static/sounds"
        )
        app.logger.info(f"Serving sound file {filename} from {static_dir}")
        return send_from_directory(static_dir, filename)

    return app
