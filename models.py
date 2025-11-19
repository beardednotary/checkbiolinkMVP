from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    plan = db.Column(db.String(20), default='starter')  # starter, pro, business
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    
    # Relationships
    links = db.relationship('Link', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'


class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    name = db.Column(db.String(100))  # Friendly name for the link
    status = db.Column(db.String(20), default='unknown')  # up, down, unknown
    last_checked = db.Column(db.DateTime)
    last_status_change = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    
    # Relationships
    checks = db.relationship('LinkCheck', backref='link', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Link {self.url}>'


class LinkCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey('link.id'), nullable=False)
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
    status_code = db.Column(db.Integer)
    response_time = db.Column(db.Float)  # in seconds
    is_up = db.Column(db.Boolean)
    error_message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<LinkCheck {self.link_id} at {self.checked_at}>'