from app.extensions import db
from .enums import Gender

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) 
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.Enum(Gender), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    church_id = db.Column(db.Integer, db.ForeignKey('churches.id'), nullable=True)
    denomination_id = db.Column(db.Integer, db.ForeignKey('denominations.id'), nullable=True)
    updated_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())

    def __repr__(self):
        return (
            f"User("
            f"id={self.id}, "
            f"role_id={self.role_id}, "
            f"email='{self.email}', "
            f"password='{self.password}', "
            f"first_name='{self.first_name}', "
            f"last_name='{self.last_name}', "
            f"phone='{self.phone}', "
            f"gender={self.gender}, "
            f"age={self.age}, "
            f"church_id={self.church_id}, "
            f"denomination_id={self.denomination_id}, "
            f"updated_at={self.updated_at}, "
            f"created_at={self.created_at}"
            f")"
        )