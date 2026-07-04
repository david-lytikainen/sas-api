from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
import sentry_sdk
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.extensions import db, jwt
from app.utils.email import mail
from datetime import timedelta
import logging
from sentry_sdk.integrations.flask import FlaskIntegration

# Load environment variables
load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def _get_required_origins() -> list[str]:
    origins = [origin.strip() for origin in _require_env("CORS_ORIGINS").split(",")]
    origins = [origin for origin in origins if origin]
    if not origins:
        raise RuntimeError("CORS_ORIGINS must include at least one allowed origin.")
    return origins


def _init_sentry(app: Flask) -> None:
    sentry_dsn = os.getenv("SENTRY_DSN", "").strip()
    if not sentry_dsn:
        app.logger.info("Sentry is not configured; skipping error monitoring init.")
        return

    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FlaskIntegration()],
        environment=os.getenv(
            "SENTRY_ENVIRONMENT", os.getenv("FLASK_ENV", "production")
        ),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0")),
    )
    app.logger.info("Sentry error monitoring initialized.")


def create_app():
    app = Flask(__name__)

    # Set testing mode from environment variable
    app.config["TESTING"] = os.getenv("FLASK_ENV") in ["development", "testing"]

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)
    _init_sentry(app)

    # Configure database
    app.config["SQLALCHEMY_DATABASE_URI"] = _require_env("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Configure JWT
    app.config["JWT_SECRET_KEY"] = _require_env("JWT_SECRET_KEY")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
        days=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_DAYS", 365))
    )
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"

    # Email configuration
    app.config["MAIL_SERVER"] = _require_env("MAIL_SERVER")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() in [
        "true",
        "1",
        "t",
    ]
    app.config["MAIL_USERNAME"] = _require_env("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = _require_env("MAIL_PASSWORD")
    app.config["CLIENT_URL"] = _require_env("CLIENT_URL")
    app.config["STRIPE_SECRET_KEY"] = _require_env("STRIPE_SECRET_KEY")
    app.config["STRIPE_WEBHOOK_SECRET"] = _require_env("STRIPE_WEBHOOK_SECRET")
    app.config["STRIPE_CONNECT_COUNTRY"] = os.getenv(
        "STRIPE_CONNECT_COUNTRY", "US"
    )  # TODO: change if platform country differs
    app.config["STRIPE_CONNECT_REFRESH_URL"] = _require_env(
        "STRIPE_CONNECT_REFRESH_URL"
    )
    app.config["STRIPE_CONNECT_RETURN_URL"] = _require_env(
        "STRIPE_CONNECT_RETURN_URL"
    )
    app.config["STRIPE_CHECKOUT_SUCCESS_URL"] = _require_env(
        "STRIPE_CHECKOUT_SUCCESS_URL"
    )
    app.config["STRIPE_CHECKOUT_CANCEL_URL"] = _require_env(
        "STRIPE_CHECKOUT_CANCEL_URL"
    )

    # Implement rate limiting using flask-limiter
    Limiter(
        get_remote_address,
        app=app,
        default_limits=["150 per minute, 10000 per hour, 100000 per day"],
        strategy="fixed-window",
    )

    # Initialize Flask extensions
    db.init_app(app)
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
    cors_origins = _get_required_origins()
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
