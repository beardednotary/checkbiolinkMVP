import os

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this'
    
    # Database - use PostgreSQL in production, SQLite in development
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///checkbiolink.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mailgun configuration - MUST be set via environment variables
    MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY')
    MAILGUN_DOMAIN = os.environ.get('MAILGUN_DOMAIN') or 'sandboxa07f7ff10be44fd792dc8f71dc855657.mailgun.org'
    
    # Check intervals (in seconds)
    CHECK_INTERVALS = {
        'starter': 14400,   # 4 hours (6x daily)
        'pro': 7200,        # 2 hours (12x daily)
        'business': 3600    # 1 hour (24x daily)
    }
    
    # Plan limits
    PLAN_LIMITS = {
        'starter': 3,
        'pro': 10,
        'business': 50
    }