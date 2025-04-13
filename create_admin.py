from app import create_app
from app.models import User
from app.extensions import db
from werkzeug.security import generate_password_hash
from app.models.enums import Gender

def create_admin_user():
    app = create_app()
    with app.app_context():
        # Check if admin already exists
        admin = User.query.filter_by(email='admin@example.com').first()
        if not admin:
            admin = User(
                email='admin@example.com',
                password=generate_password_hash('admin123'),
                role_id=1,  # Admin role
                first_name='Admin',
                last_name='User',
                phone='1234567890',
                gender=Gender.NOT_SPECIFIED,
                age=30
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully!")
        else:
            print("Admin user already exists!")

if __name__ == '__main__':
    create_admin_user() 