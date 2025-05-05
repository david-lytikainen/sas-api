import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # relative imports

from app import create_app, db
from app.models.enums import UserRole
from sqlalchemy.sql import text

def initialize_basic_data():
    """Initialize basic data like roles"""
    app = create_app()
    with app.app_context():
        # Initialize roles
        print("Initializing roles...")
        try:
            # Insert roles directly using SQL
            db.session.execute(
                text("""
                INSERT INTO roles (id, name, permission_level) 
                VALUES 
                (1, 'User', 1),
                (2, 'Organizer', 2),
                (3, 'Admin', 3)
                ON CONFLICT (id) DO NOTHING;
                """)
            )
            db.session.commit()
            print("Roles initialized successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error initializing roles: {e}")

if __name__ == "__main__":
    initialize_basic_data() 