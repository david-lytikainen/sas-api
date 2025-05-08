import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # relative imports

from app import create_app, db
from app.models.enums import EventStatus
from sqlalchemy.sql import text


def rebuild_database():
    """Recreate all database tables with correct enums"""
    app = create_app()
    with app.app_context():
        # Drop all tables
        print("Dropping all tables...")
        db.drop_all()

        # Drop the enum type if it exists
        try:
            db.session.execute(text("DROP TYPE IF EXISTS eventstatus;"))
            db.session.commit()
            print("Dropped existing eventstatus enum")
        except Exception as e:
            db.session.rollback()
            print(f"Error dropping eventstatus enum (may not exist): {e}")

        # Create the enum type with correct values
        try:
            values = ", ".join(f"'{val.value}'" for val in EventStatus)
            db.session.execute(text(f"CREATE TYPE eventstatus AS ENUM ({values});"))
            db.session.commit()
            print(
                f"Created eventstatus enum with values: {[val.value for val in EventStatus]}"
            )
        except Exception as e:
            db.session.rollback()
            print(f"Error creating eventstatus enum: {e}")

        # Create all tables
        print("Creating all tables...")
        db.create_all()
        print("Database rebuilt successfully!")


if __name__ == "__main__":
    rebuild_database()
