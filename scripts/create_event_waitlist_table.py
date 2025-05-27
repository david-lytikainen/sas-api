import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv

    dotenv_path = os.path.join(project_root, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print("Loaded environment variables from .env file.")
except ImportError:
    print(
        "python-dotenv not installed, skipping .env file loading. Ensure environment variables are set."
    )

from app import create_app, db
from app.models.event_waitlist import EventWaitlist


def create_table():
    """
    Creates the event_waitlists table in the database if it doesn't already exist,
    based on the EventWaitlist SQLAlchemy model.
    """
    flask_env = os.getenv(
        "FLASK_ENV", "development"
    )  # Default to development if not set
    flask_config_name = (
        os.getenv("FLASK_CONFIG") or "default"
    )  # This might be used internally by create_app or its config loading

    print(
        f"Initializing Flask app (FLASK_ENV='{flask_env}', FLASK_CONFIG='{flask_config_name}' will be used if app configured to read them)..."
    )
    app = create_app()  # Call without arguments

    with app.app_context():
        print(
            f"Attempting to create table '{EventWaitlist.__tablename__}' if it doesn't exist..."
        )
        try:
            # Use checkfirst=True to prevent errors if the table already exists
            EventWaitlist.__table__.create(bind=db.engine, checkfirst=True)
            print(f"Table '{EventWaitlist.__tablename__}' creation process completed.")
            print("If the table already existed, no action was taken.")

            # Verify table creation by inspecting the database metadata
            inspector = db.inspect(db.engine)
            if EventWaitlist.__tablename__ in inspector.get_table_names():
                print(
                    f"Successfully verified that table '{EventWaitlist.__tablename__}' exists."
                )
            else:
                print(
                    f"Verification failed: Table '{EventWaitlist.__tablename__}' does not appear to exist after creation attempt."
                )

        except Exception as e:
            print(f"An error occurred during table creation: {e}")
            print(
                "Please ensure the database is running and accessible, and that prerequisite tables (users, events) exist if foreign key checks are immediate."
            )


if __name__ == "__main__":
    create_table()
