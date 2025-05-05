import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # relative imports

from app import create_app, db
from flask_migrate import upgrade

def fix_database():
    """Apply migrations to fix the database schema"""
    app = create_app()
    with app.app_context():
        print("Applying database migrations...")
        upgrade()
        print("Database migrations applied successfully!")

if __name__ == "__main__":
    fix_database() 