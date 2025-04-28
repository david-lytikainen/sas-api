from datetime import datetime
from app import create_app
from app.models import User
from app.extensions import db
from werkzeug.security import generate_password_hash
from app.models.enums import Gender

def create_admin_user(update=False):
    app = create_app()
    with app.app_context():
        # Check if admin already exists
        admin = User.query.filter_by(email='admin@example.com').first()
        if not admin:
            admin = User(
                email='admin@example.com',
                password=generate_password_hash('admin123'),
                role_id=3,  # Admin role
                first_name='Admin',
                last_name='User',
                phone='1234567890',
                gender=Gender.MALE,
                birthday=datetime(1990, 1, 1)
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
        elif update:
            admin.password = generate_password_hash('admin123')
            admin.role_id = 3
            db.session.commit()
            print("Admin user updated successfully!")
        else:
            print("Admin user already exists!")

if __name__ == '__main__':
    create_admin_user(update=True) 