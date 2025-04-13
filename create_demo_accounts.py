"""
Script to create or update demo accounts for the SAS application.
"""

from app import create_app
from app.models import User, Role
from app.models.enums import Gender
from app.extensions import db
from werkzeug.security import generate_password_hash

def main():
    """Create or update demo accounts with correct credentials."""
    app = create_app()
    with app.app_context():
        # Ensure roles exist
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', permission_level=100)
            db.session.add(admin_role)
            db.session.commit()
            print("Created admin role")
        
        attendee_role = Role.query.filter_by(name='attendee').first()
        if not attendee_role:
            attendee_role = Role(name='attendee', permission_level=10)
            db.session.add(attendee_role)
            db.session.commit()
            print("Created attendee role")
        
        # Create or update admin account
        admin = User.query.filter_by(email='admin@example.com').first()
        if admin:
            admin.password = generate_password_hash('password')
            db.session.commit()
            print("Updated admin password")
        else:
            admin = User(
                email='admin@example.com',
                password=generate_password_hash('password'),
                role_id=admin_role.id,
                first_name='Admin',
                last_name='User',
                phone='123-456-7890',
                gender=Gender.NOT_SPECIFIED,
                age=30
            )
            db.session.add(admin)
            db.session.commit()
            print(f"Created admin user with ID: {admin.id}")
        
        # Create or update attendee account
        attendee = User.query.filter_by(email='attendee@example.com').first()
        if attendee:
            attendee.password = generate_password_hash('password')
            db.session.commit()
            print("Updated attendee password")
        else:
            attendee = User(
                email='attendee@example.com',
                password=generate_password_hash('password'),
                role_id=attendee_role.id,
                first_name='Attendee',
                last_name='User',
                phone='123-456-7890',
                gender=Gender.NOT_SPECIFIED,
                age=25
            )
            db.session.add(attendee)
            db.session.commit()
            print(f"Created attendee user with ID: {attendee.id}")
        
        print("Demo accounts setup complete!")

if __name__ == "__main__":
    main() 