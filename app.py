from flask import Flask, render_template, request, jsonify, redirect, url_for
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
import stripe

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# CSRF protection for JSON API endpoints
@app.before_request
def csrf_check():
    if request.method in ('POST', 'PUT', 'DELETE'):
        # Exempt webhook and cron endpoints (they use their own auth)
        exempt = ('/webhook/stripe', '/api/check-all')
        if request.path in exempt:
            return
        # Require JSON content type on mutating requests
        if request.content_type and 'application/json' not in request.content_type:
            return jsonify({'error': 'Invalid content type'}), 400

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
    """Register a new user with 14-day trial"""
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400

    # Create user with 14-day trial
    user = User(
        email=email, 
        plan='starter',
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
        subscription_status='trial'
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)

    return jsonify({
        'message': 'Registration successful',
        'user': {
            'id': user.id, 
            'email': user.email, 
            'plan': user.plan,
            'trial_ends_at': user.trial_ends_at.isoformat(),
            'days_left': user.days_left_in_trial
        }
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
            'user': {
                'id': user.id, 
                'email': user.email, 
                'plan': user.plan,
                'subscription_status': user.subscription_status,
                'days_left': user.days_left_in_trial if user.subscription_status == 'trial' else None
            }
        })

    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    logout_user()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/user/status')
@login_required
def user_status():
    """Get current user's status, plan limits, and trial info"""
    return jsonify({
        'email': current_user.email,
        'plan': current_user.plan,
        'subscription_status': current_user.subscription_status,
        'trial_ends_at': current_user.trial_ends_at.isoformat() if current_user.trial_ends_at else None,
        'days_left_in_trial': current_user.days_left_in_trial,
        'is_trial_active': current_user.is_trial_active,
        'can_use_service': current_user.can_use_service,
        'links_count': len(current_user.links),
        'links_limit': current_user.link_limit,
        'can_add_links': current_user.can_add_links,
        'stripe_customer_id': current_user.stripe_customer_id
    })


@app.route('/api/links', methods=['GET'])
@login_required
def get_links():
    """Get all links for current user"""
    # Check if user can use the service
    if not current_user.can_use_service:
        return jsonify({
            'error': 'Your trial has expired. Please subscribe to continue.',
            'trial_expired': True,
            'links': []
        }), 403
    
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
    # Check if user can use the service
    if not current_user.can_use_service:
        return jsonify({
            'error': 'Your trial has expired. Please subscribe to continue monitoring your links.',
            'trial_expired': True
        }), 403
    
    # Check if user can add more links
    if not current_user.can_add_links:
        return jsonify({
            'error': f'Link limit reached. Your {current_user.plan} plan allows {current_user.link_limit} links. Upgrade to add more.',
            'limit_reached': True,
            'current_plan': current_user.plan,
            'current_count': len(current_user.links),
            'limit': current_user.link_limit
        }), 403
    
    data = request.json
    url = data.get('url')
    name = data.get('name', '')

    if not url:
        return jsonify({'error': 'URL required'}), 400

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

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        print(f"Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        print(f"Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_completed(session)
    
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_updated(subscription)
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_deleted(subscription)
    
    return jsonify({'status': 'success'}), 200

@app.route('/api/check-link-now', methods=['POST'])
def check_link_now():
    """Free instant link checker - no auth required"""
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL required'}), 400
    
    # Use your existing check_url function
    from link_monitor import check_url
    result = check_url(url)
    
    return jsonify({
        'url': url,
        'is_up': result['is_up'],
        'status_code': result['status_code'],
        'response_time': result['response_time'],
        'error_message': result['error_message']
    })


def handle_checkout_completed(session):
    """Handle successful checkout - activate user subscription"""
    customer_email = session.get('customer_details', {}).get('email')
    customer_id = session.get('customer')
    subscription_id = session.get('subscription')
    
    print(f"✅ Checkout completed for {customer_email}")
    
    # Find user by email
    user = User.query.filter_by(email=customer_email).first()
    
    if user:
        # Get subscription details to determine plan
        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            price_id = subscription['items']['data'][0]['price']['id']
            
            # Map price to plan (you'll need to update these price IDs)
            plan = get_plan_from_price(price_id)
            
            user.subscription_status = 'active'
            user.stripe_customer_id = customer_id
            user.stripe_subscription_id = subscription_id
            user.plan = plan
            user.trial_ends_at = None  # Clear trial since they're now paid
            
            db.session.commit()
            print(f"✅ User {customer_email} upgraded to {plan} plan")
    else:
        # New user from direct payment link - create account
        # They'll need to set password later
        print(f"⚠️ No existing user found for {customer_email}")
        # Optionally create a new user here


def handle_subscription_updated(subscription):
    """Handle subscription changes (upgrades, downgrades)"""
    customer_id = subscription.get('customer')
    status = subscription.get('status')
    price_id = subscription['items']['data'][0]['price']['id']
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    
    if user:
        if status == 'active':
            user.subscription_status = 'active'
            user.plan = get_plan_from_price(price_id)
        elif status == 'past_due':
            user.subscription_status = 'past_due'
        elif status == 'canceled':
            user.subscription_status = 'canceled'
        
        db.session.commit()
        print(f"✅ Subscription updated for {user.email}: {status}")


def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    customer_id = subscription.get('customer')
    
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    
    if user:
        user.subscription_status = 'canceled'
        user.plan = 'starter'  # Downgrade to starter
        db.session.commit()
        print(f"✅ Subscription canceled for {user.email}")


def get_plan_from_price(price_id):
    """Map Stripe price ID to plan name"""
    # UPDATE THESE WITH YOUR ACTUAL STRIPE PRICE IDs
    # Find them in Stripe Dashboard > Products > Click product > Copy price ID
    price_to_plan = {
        os.environ.get('STRIPE_PRICE_STARTER', ''): 'starter',
        os.environ.get('STRIPE_PRICE_PRO', ''): 'pro',
        os.environ.get('STRIPE_PRICE_BUSINESS', ''): 'business',
    }
    
    return price_to_plan.get(price_id, 'starter')


@app.route('/payment-success')
def payment_success():
    """Page shown after successful payment"""
    return render_template('payment_success.html')

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
    
    # Try to add new columns if they don't exist (migration)
    from sqlalchemy import text, inspect
    try:
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user')]
        
        with db.engine.connect() as conn:
            if 'trial_ends_at' not in columns:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN trial_ends_at TIMESTAMP'))
                conn.commit()
                print("✅ Added trial_ends_at column")
            
            if 'subscription_status' not in columns:
                conn.execute(text("ALTER TABLE \"user\" ADD COLUMN subscription_status VARCHAR(20) DEFAULT 'trial'"))
                conn.commit()
                print("✅ Added subscription_status column")
            
            if 'stripe_customer_id' not in columns:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN stripe_customer_id VARCHAR(100)'))
                conn.commit()
                print("✅ Added stripe_customer_id column")
            
            if 'stripe_subscription_id' not in columns:
                conn.execute(text('ALTER TABLE "user" ADD COLUMN stripe_subscription_id VARCHAR(100)'))
                conn.commit()
                print("✅ Added stripe_subscription_id column")
                
        print("✅ Database migration completed successfully")
    except Exception as e:
        print(f"⚠️ Migration note: {e}")

    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("Scheduler started - checking links every 10 minutes")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)