import requests
import time
from datetime import datetime
from models import db, Link, LinkCheck

def check_url(url, timeout=10):
    """
    Check if a URL is accessible and return status information
    
    Returns:
        dict: {
            'is_up': bool,
            'status_code': int or None,
            'response_time': float,
            'error_message': str or None
        }
    """
    start_time = time.time()
    
    try:
        response = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={'User-Agent': 'CheckBioLink/1.0'}
        )
        response_time = time.time() - start_time
        
        # Consider 2xx and 3xx as "up"
        is_up = 200 <= response.status_code < 400
        
        return {
            'is_up': is_up,
            'status_code': response.status_code,
            'response_time': response_time,
            'error_message': None if is_up else f'HTTP {response.status_code}'
        }
        
    except requests.exceptions.Timeout:
        return {
            'is_up': False,
            'status_code': None,
            'response_time': time.time() - start_time,
            'error_message': 'Request timeout'
        }
    except requests.exceptions.ConnectionError:
        return {
            'is_up': False,
            'status_code': None,
            'response_time': time.time() - start_time,
            'error_message': 'Connection error'
        }
    except requests.exceptions.RequestException as e:
        return {
            'is_up': False,
            'status_code': None,
            'response_time': time.time() - start_time,
            'error_message': str(e)
        }


def check_link(link_id):
    """
    Check a specific link and save results to database
    """
    link = Link.query.get(link_id)
    if not link or not link.active:
        return None
    
    print(f"Checking link: {link.url}")
    
    # Perform the check
    result = check_url(link.url)
    
    # Save check result
    check = LinkCheck(
        link_id=link.id,
        checked_at=datetime.utcnow(),
        status_code=result['status_code'],
        response_time=result['response_time'],
        is_up=result['is_up'],
        error_message=result['error_message']
    )
    db.session.add(check)
    
    # Update link status
    old_status = link.status
    new_status = 'up' if result['is_up'] else 'down'
    
    link.last_checked = datetime.utcnow()
    
    # If status changed, update last_status_change
    if old_status != new_status:
        link.last_status_change = datetime.utcnow()
        link.status = new_status
        print(f"Status changed from {old_status} to {new_status}")
        
        # Send alert if link went down
        if new_status == 'down':
            send_alert(link, result)
    else:
        link.status = new_status
    
    db.session.commit()
    
    return result


def send_alert(link, check_result):
    """
    Send email alert when a link goes down
    """
    from app import app
    import requests as req
    
    user = link.user
    
    with app.app_context():
        subject = f"⚠️ Alert: Your Link Is Down - {link.name or link.url}"
        
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #f5576c;">⚠️ CheckBioLink Alert</h2>
                <p>We've detected that your link is currently <strong>DOWN</strong>.</p>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                    <p><strong>Link:</strong> {link.name or 'Unnamed Link'}</p>
                    <p><strong>URL:</strong> <a href="{link.url}">{link.url}</a></p>
                    <p><strong>Status:</strong> {check_result['error_message']}</p>
                    <p><strong>Time Detected:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>
                
                <p>Please check your link and fix any issues to avoid losing traffic and potential customers.</p>
                
                <p style="margin-top: 30px; color: #666; font-size: 14px;">
                    - The CheckBioLink Team<br>
                    <a href="https://checkbiolink.com">checkbiolink.com</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        try:
            response = req.post(
                f"https://api.mailgun.net/v3/{app.config['MAILGUN_DOMAIN']}/messages",
                auth=("api", app.config['MAILGUN_API_KEY']),
                data={
                    "from": f"CheckBioLink Alerts <alerts@{app.config['MAILGUN_DOMAIN']}>",
                    "to": user.email,
                    "subject": subject,
                    "html": html_body
                }
            )
            
            if response.status_code == 200:
                print(f"Alert sent to {user.email}")
            else:
                print(f"Failed to send alert: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error sending alert: {str(e)}")


def check_all_links():
    """
    Check all active links for all active users
    """
    from app import app
    
    with app.app_context():
        links = Link.query.filter_by(active=True).all()
        print(f"Checking {len(links)} links...")
        
        for link in links:
            try:
                check_link(link.id)
                time.sleep(1)  # Small delay between checks
            except Exception as e:
                print(f"Error checking link {link.id}: {str(e)}")
        
        print(f"Completed checking {len(links)} links")