from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with job applications
    applications = db.relationship('Application', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set the user's password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches the hash"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        """Return user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f'<User {self.email}>'


class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    position = db.Column(db.String(200), nullable=False)
    date_applied = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200))
    salary = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    # File uploads
    resume_path = db.Column(db.String(255))
    cover_letter_path = db.Column(db.String(255))
    
    # Interview details
    interview_date = db.Column(db.DateTime)
    interview_notes = db.Column(db.Text)
    feedback = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert application to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'company': self.company,
            'position': self.position,
            'dateApplied': self.date_applied.isoformat(),
            'status': self.status,
            'location': self.location,
            'salary': self.salary,
            'notes': self.notes,
            'interviewDate': self.interview_date.isoformat() if self.interview_date else None,
            'interviewNotes': self.interview_notes,
            'feedback': self.feedback,
            'resumePath': self.resume_path,
            'coverLetterPath': self.cover_letter_path
        }
    
    def __repr__(self):
        return f'<Application {self.company} - {self.position}>'