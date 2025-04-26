import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # relative imports

from app import create_app
from app.models import Role
from app.extensions import db


def setup_roles():
    app = create_app()
    with app.app_context():
        # Create roles if they don't exist
        roles = [
            {"id": 1, "name": "User", "permission_level": 1},
            {"id": 2, "name": "Organizer", "permission_level": 2},
            {"id": 3, "name": "Admin", "permission_level": 3},
        ]

        for role_data in roles:
            role = Role.query.filter_by(id=role_data["id"]).first()
            if not role:
                role = Role(**role_data)
                db.session.add(role)
                print(f"Created role: {role_data['name']}")

        db.session.commit()
        print("Roles setup completed!")


if __name__ == "__main__":
    setup_roles()
