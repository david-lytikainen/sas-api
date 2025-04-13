from app.extensions import db
from datetime import date
from .enums import Gender
from datetime import datetime

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
    birthday = db.Column(db.Date, nullable=False)
    church_id = db.Column(db.Integer, db.ForeignKey('churches.id'), nullable=True)
    denomination_id = db.Column(db.Integer, db.ForeignKey('denominations.id'), nullable=True)
    denomination = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now(), onupdate=db.func.now())
    created_at = db.Column(db.TIMESTAMP(timezone=True), nullable=False, server_default=db.func.now())

    def calculate_age(self):
        today = date.today()
        return today.year - self.birthday.year - ((today.month, today.day) < (self.birthday.month, self.birthday.day)) 
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, User):
            return self.id == other.id
        return False
    
    def to_dict(self):
        return {
            'id': self.id,
            'role_id': self.role_id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone': self.phone,
            'gender': self.gender.value if self.gender else None,
            'age': self.age,
            'church_id': self.church_id,
            'denomination_id': self.denomination_id,
            'church': self.church.name if self.church_id and hasattr(self, 'church') and self.church else None,
            'denomination': self.denomination.name if self.denomination_id and hasattr(self, 'denomination') and self.denomination else None,
            'denomination_custom': self.denomination,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return (
            f"User("
            f"id={self.id}, "
            f"age={self.calculate_age()}, "
            f"first_name='{self.first_name}', "
            f"last_name='{self.last_name}', "
            f"gender={self.gender}"
            f")\n"
        )