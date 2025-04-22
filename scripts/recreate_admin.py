import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # relative imports

from app import create_app
from app.models import User
from app.extensions import db
from werkzeug.security import generate_password_hash
from app.models.enums import Gender
from datetime import datetime, timedelta


def recreate_admin_user():
    app = create_app()
    with app.app_context():
        # Delete existing admin
        admin = User.query.filter_by(email="admin@example.com").first()
        if admin:
            db.session.delete(admin)
            db.session.commit()
            print("Existing admin user deleted.")

        # Create new admin with role 3
        new_admin = User(
            email="admin@example.com",
            password=generate_password_hash("admin123"),
            role_id=3,  # Admin role
            first_name="Admin",
            last_name="User",
            phone="1234567890",
            gender=Gender.MALE,
            birthday=datetime.now() - timedelta(days=30 * 365),
            church_id=None,
            denomination_id=None,
        )
        db.session.add(new_admin)
        db.session.commit()
        print("New admin user created successfully with role 3!")


if __name__ == "__main__":
    recreate_admin_user()
