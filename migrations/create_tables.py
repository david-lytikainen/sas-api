import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db


def create_tables():
    app = create_app()
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Created all database tables successfully!")

if __name__ == "__main__":
    create_tables() 