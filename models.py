from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    plan = db.Column(db.String(20), default='starter')  # starter, pro, business
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    
    # Trial & Subscription fields
    trial_ends_at = db.Column(db.DateTime)
    subscription_status = db.Column(db.String(20), default='trial')  # trial, active, canceled, expired
    stripe_customer_id = db.Column(db.String(100))
    stripe_subscription_id = db.Column(db.String(100))
    
    # Relationships
    links = db.relationship('Link', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_trial_active(self):
        """Check if user's trial period is still active"""
        if not self.trial_ends_at:
            return False
        return datetime.utcnow() < self.trial_ends_at
    
    @property
    def days_left_in_trial(self):
        """Calculate days remaining in trial"""
        if not self.trial_ends_at:
            return 0
        delta = self.trial_ends_at - datetime.utcnow()
        return max(0, delta.days)
    
    @property
    def can_add_links(self):
        """Check if user can add more links based on trial/subscription status and plan limits"""
        # Check if trial active or paid
        if self.subscription_status == 'trial' and not self.is_trial_active:
            return False
        if self.subscription_status in ['canceled', 'expired']:
            return False
        
        # Check link limits based on plan
        plan_limits = {'starter': 3, 'pro': 10, 'business': 50}
        current_count = len(self.links)
        max_links = plan_limits.get(self.plan, 3)
        
        return current_count < max_links
    
    @property
    def link_limit(self):
        """Get the maximum number of links for user's plan"""
        plan_limits = {'starter': 3, 'pro': 10, 'business': 50}
        return plan_limits.get(self.plan, 3)
    
    @property
    def can_use_service(self):
        """Check if user can use the service (trial active or paid subscription)"""
        if self.subscription_status == 'trial':
            return self.is_trial_active
        return self.subscription_status == 'active'
    
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