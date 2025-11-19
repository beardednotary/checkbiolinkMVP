from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Link, LinkCheck
from config import Config
from link_monitor import cfrom flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Link, LinkCheck
from config import Config
from link_monitor import check_link, check_all_links
import schedule
import threading
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Routes
@app.route('/')
def index():
    return render_template('dashboard.html')
    return render_template('dashboard_app.html')


@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400

    user = User(email=email, plan='starter')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)

    return jsonify({
        'message': 'Registration successful',
        'user': {'id': user.id, 'email': user.email, 'plan': user.plan}
    }), 201


@app.route('/api/login', methods=['POST'])
def login():
    """Login existing user"""
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if user and user.check_password(password):
        login_user(user)
        return jsonify({
            'message': 'Login successful',
            'user': {'id': user.id, 'email': user.email, 'plan': user.plan}
        })

    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    logout_user()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/links', methods=['GET'])
@login_required
def get_links():
    """Get all links for current user"""
    links = Link.query.filter_by(user_id=current_user.id, active=True).all()

    return jsonify({
        'links': [{
            'id': link.id,
            'url': link.url,
            'name': link.name,
            'status': link.status,
            'last_checked': link.last_checked.isoformat() if link.last_checked else None,
            'created_at': link.created_at.isoformat()
        } for link in links]
    })


@app.route('/api/links', methods=['POST'])
@login_required
def add_link():
    """Add a new link to monitor"""
    data = request.json
    url = data.get('url')
    name = data.get('name', '')

    if not url:
        return jsonify({'error': 'URL required'}), 400

    # Check plan limits
    current_links_count = Link.query.filter_by(user_id=current_user.id, active=True).count()
    plan_limit = app.config['PLAN_LIMITS'].get(current_user.plan, 3)

    if current_links_count >= plan_limit:
        return jsonify({'error': f'Link limit reached for {current_user.plan} plan'}), 403

    # Add http:// if not present
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    link = Link(user_id=current_user.id, url=url, name=name)
    db.session.add(link)
    db.session.commit()

    # Perform initial check
    check_link(link.id)

    return jsonify({
        'message': 'Link added successfully',
        'link': {
            'id': link.id,
            'url': link.url,
            'name': link.name,
            'status': link.status
        }
    }), 201


@app.route('/api/links/<int:link_id>', methods=['DELETE'])
@login_required
def delete_link(link_id):
    """Delete a link"""
    link = Link.query.get_or_404(link_id)

    if link.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    link.active = False
    db.session.commit()

    return jsonify({'message': 'Link deleted successfully'})


@app.route('/api/links/<int:link_id>/check', methods=['POST'])
@login_required
def manual_check(link_id):
    """Manually trigger a link check"""
    link = Link.query.get_or_404(link_id)

    if link.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    result = check_link(link_id)

    return jsonify({
        'message': 'Check completed',
        'result': result
    })


@app.route('/api/links/<int:link_id>/history', methods=['GET'])
@login_required
def get_link_history(link_id):
    """Get check history for a link"""
    link = Link.query.get_or_404(link_id)

    if link.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Get last 100 checks
    checks = LinkCheck.query.filter_by(link_id=link_id).order_by(LinkCheck.checked_at.desc()).limit(100).all()

    return jsonify({
        'history': [{
            'checked_at': check.checked_at.isoformat(),
            'is_up': check.is_up,
            'status_code': check.status_code,
            'response_time': check.response_time,
            'error_message': check.error_message
        } for check in checks]
    })

@app.route('/api/check-all', methods=['POST'])
def trigger_check_all():
    """Endpoint to trigger all checks (for external cron)"""
    auth_token = request.headers.get('Authorization')

    # Simple token authentication
    expected_token = f"Bearer {app.config['SECRET_KEY']}"
    if auth_token != expected_token:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        check_all_links()
        return jsonify({'message': 'All links checked successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Scheduler
def run_scheduler():
    """Run the monitoring scheduler in a background thread"""
    schedule.every(10).minutes.do(check_all_links)

    while True:
        schedule.run_pending()
        time.sleep(60)


# Initialize database and start scheduler
with app.app_context():
    db.create_all()

    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("Scheduler started - checking links every 10 minutes")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)heck_link, check_all_links
import schedule
import threading
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Routes
@app.route('/')
def index():
    return render_template('dashboard_app.html')


@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    user = User(email=email, plan='starter')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    login_user(user)
    
    return jsonify({
        'message': 'Registration successful',
        'user': {'id': user.id, 'email': user.email, 'plan': user.plan}
    }), 201


@app.route('/api/login', methods=['POST'])
def login():
    """Login existing user"""
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()
    
    if user and user.check_password(password):
        login_user(user)
        return jsonify({
            'message': 'Login successful',
            'user': {'id': user.id, 'email': user.email, 'plan': user.plan}
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    logout_user()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/links', methods=['GET'])
@login_required
def get_links():
    """Get all links for current user"""
    links = Link.query.filter_by(user_id=current_user.id, active=True).all()
    
    return jsonify({
        'links': [{
            'id': link.id,
            'url': link.url,
            'name': link.name,
            'status': link.status,
            'last_checked': link.last_checked.isoformat() if link.last_checked else None,
            'created_at': link.created_at.isoformat()
        } for link in links]
    })


@app.route('/api/links', methods=['POST'])
@login_required
def add_link():
    """Add a new link to monitor"""
    data = request.json
    url = data.get('url')
    name = data.get('name', '')
    
    if not url:
        return jsonify({'error': 'URL required'}), 400
    
    # Check plan limits
    current_links_count = Link.query.filter_by(user_id=current_user.id, active=True).count()
    plan_limit = app.config['PLAN_LIMITS'].get(current_user.plan, 3)
    
    if current_links_count >= plan_limit:
        return jsonify({'error': f'Link limit reached for {current_user.plan} plan'}), 403
    
    # Add http:// if not present
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    link = Link(user_id=current_user.id, url=url, name=name)
    db.session.add(link)
    db.session.commit()
    
    # Perform initial check
    check_link(link.id)
    
    return jsonify({
        'message': 'Link added successfully',
        'link': {
            'id': link.id,
            'url': link.url,
            'name': link.name,
            'status': link.status
        }
    }), 201


@app.route('/api/links/<int:link_id>', methods=['DELETE'])
@login_required
def delete_link(link_id):
    """Delete a link"""
    link = Link.query.get_or_404(link_id)
    
    if link.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    link.active = False
    db.session.commit()
    
    return jsonify({'message': 'Link deleted successfully'})


@app.route('/api/links/<int:link_id>/check', methods=['POST'])
@login_required
def manual_check(link_id):
    """Manually trigger a link check"""
    link = Link.query.get_or_404(link_id)
    
    if link.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    result = check_link(link_id)
    
    return jsonify({
        'message': 'Check completed',
        'result': result
    })


@app.route('/api/links/<int:link_id>/history', methods=['GET'])
@login_required
def get_link_history(link_id):
    """Get check history for a link"""
    link = Link.query.get_or_404(link_id)
    
    if link.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get last 100 checks
    checks = LinkCheck.query.filter_by(link_id=link_id).order_by(LinkCheck.checked_at.desc()).limit(100).all()
    
    return jsonify({
        'history': [{
            'checked_at': check.checked_at.isoformat(),
            'is_up': check.is_up,
            'status_code': check.status_code,
            'response_time': check.response_time,
            'error_message': check.error_message
        } for check in checks]
    })

@app.route('/api/check-all', methods=['POST'])
def trigger_check_all():
    """Endpoint to trigger all checks (for external cron)"""
    auth_token = request.headers.get('Authorization')
    
    # Simple token authentication
    expected_token = f"Bearer {app.config['SECRET_KEY']}"
    if auth_token != expected_token:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        check_all_links()
        return jsonify({'message': 'All links checked successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Scheduler
def run_scheduler():
    """Run the monitoring scheduler in a background thread"""
    schedule.every(10).minutes.do(check_all_links)
    
    while True:
        schedule.run_pending()
        time.sleep(60)


# Initialize database and start scheduler
with app.app_context():
    db.create_all()
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("Scheduler started - checking links every 10 minutes")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
