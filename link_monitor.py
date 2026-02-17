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
            'error_message': 'Connection Timeout'
        }
    except requests.exceptions.ConnectionError:
        return {
            'is_up': False,
            'status_code': None,
            'response_time': time.time() - start_time,
            'error_message': 'Connection Error'
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


def get_error_detail(error_message):
    """
    Return a human-readable detail line for known error types
    """
    if not error_message:
        return 'An unknown error occurred'
    
    error_map = {
        'Connection Timeout': 'Server failed to respond within 10 seconds',
        'Connection Error': 'Unable to establish a connection to the server',
        'Request timeout': 'Server failed to respond within 10 seconds',
        'Connection error': 'Unable to establish a connection to the server',
    }
    
    for key, detail in error_map.items():
        if key.lower() in error_message.lower():
            return detail
    
    # For HTTP errors
    if error_message.startswith('HTTP '):
        code = error_message.replace('HTTP ', '')
        http_map = {
            '404': 'Page not found - the URL may have changed or been deleted',
            '500': 'Server error - the server encountered an internal problem',
            '503': 'Service unavailable - the server is temporarily down',
            '502': 'Bad gateway - the server received an invalid response',
            '403': 'Forbidden - access to this URL is not allowed',
        }
        return http_map.get(code, f'Server returned an error response ({error_message})')
    
    return error_message


def send_alert(link, check_result):
    """
    Send email alert when a link goes down
    """
    from app import app
    import requests as req
    
    user = link.user
    link_name = link.name or link.url
    error_type = check_result['error_message'] or 'Unknown Error'
    error_detail = get_error_detail(check_result['error_message'])
    detected_at = datetime.utcnow().strftime('%b %d, %Y at %I:%M %p UTC')
    dashboard_url = 'https://app.checkbiolink.com'

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
</head>
<body style="margin:0; padding:20px; background:#f5f5f5; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">

  <div style="max-width:600px; margin:0 auto; background:white; border:1px solid #e0e0e0; border-radius:8px; overflow:hidden;">

    <!-- Header -->
    <div style="padding:20px 24px; background:#fff; border-bottom:3px solid #ef4444;">
      <div style="font-size:18px; font-weight:700; color:#1a1a1a;">CheckBioLink</div>
      <div style="display:inline-block; background:#ef4444; color:white; padding:4px 12px; border-radius:4px; font-size:13px; font-weight:600; margin-top:8px;">&#9888; Link Down</div>
    </div>

    <!-- Body -->
    <div style="padding:32px 24px;">

      <div style="font-size:16px; color:#2a2a2a; line-height:1.6; margin-bottom:24px;">
        One of your monitored links is currently down. Your visitors may be getting an error instead of your content.
      </div>

      <!-- Affected Link -->
      <div style="background:#fef2f2; border-left:4px solid #ef4444; padding:16px; margin:24px 0; border-radius:4px;">
        <div style="font-size:12px; color:#666; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">Affected Link</div>
        <div style="font-size:15px; font-weight:600; color:#1a1a1a; margin-bottom:4px;">{link_name}</div>
        <div style="font-size:14px; color:#6b7280; word-break:break-all;">{link.url}</div>
      </div>

      <!-- Error Type -->
      <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:6px; padding:16px; margin:20px 0;">
        <div style="font-size:13px; color:#6b7280; margin-bottom:8px;">Error Type</div>
        <div style="font-size:14px; color:#1f2937; font-family:'Courier New', monospace; background:white; padding:8px 12px; border-radius:4px; border:1px solid #e5e7eb;">{error_type}</div>
      </div>

      <!-- Error Detail -->
      <div style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:6px; padding:16px; margin:20px 0;">
        <div style="font-size:13px; color:#6b7280; margin-bottom:8px;">Details</div>
        <div style="font-size:14px; color:#1f2937; font-family:'Courier New', monospace; background:white; padding:8px 12px; border-radius:4px; border:1px solid #e5e7eb;">{error_detail}</div>
      </div>

      <!-- CTA -->
      <a href="{dashboard_url}" style="display:inline-block; background:#3b82f6; color:white; padding:12px 24px; border-radius:6px; text-decoration:none; font-weight:500; margin-top:24px; font-size:14px;">View Dashboard &#8594;</a>

      <!-- Timestamp -->
      <div style="font-size:13px; color:#9ca3af; margin-top:20px; padding-top:20px; border-top:1px solid #f3f4f6;">
        Detected: {detected_at}
      </div>

    </div>

    <!-- Footer -->
    <div style="padding:20px 24px; background:#fafafa; border-top:1px solid #e5e7eb; font-size:13px; color:#6b7280; text-align:center;">
      CheckBioLink &middot; Monitoring your links 24/7
    </div>

  </div>

</body>
</html>"""

    with app.app_context():
        subject = f"Link Down: {link_name}"

        try:
            response = req.post(
                f"https://api.mailgun.net/v3/{app.config['MAILGUN_DOMAIN']}/messages",
                auth=("api", app.config['MAILGUN_API_KEY']),
                data={
                    "from": f"CheckBioLink <alerts@{app.config['MAILGUN_DOMAIN']}>",
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
    Check links based on their user's plan frequency
    """
    from app import app
    from datetime import timedelta
    
    with app.app_context():
        links = Link.query.filter_by(active=True).all()
        print(f"Found {len(links)} active links to check...")
        
        checked_count = 0
        
        for link in links:
            try:
                user = link.user
                
                # Determine check frequency based on plan
                if user.plan == 'starter':
                    check_interval = timedelta(hours=4)
                elif user.plan == 'pro':
                    check_interval = timedelta(hours=2)
                elif user.plan == 'business':
                    check_interval = timedelta(hours=1)
                else:
                    check_interval = timedelta(hours=4)  # Default
                
                # Check if enough time has passed since last check
                if link.last_checked is None:
                    should_check = True
                else:
                    time_since_check = datetime.utcnow() - link.last_checked
                    should_check = time_since_check >= check_interval
                
                if should_check:
                    check_link(link.id)
                    checked_count += 1
                    time.sleep(1)  # Small delay between checks
                else:
                    print(f"Skipping link {link.id} - checked {time_since_check.total_seconds()/3600:.1f}h ago (plan: {user.plan})")
                    
            except Exception as e:
                print(f"Error checking link {link.id}: {str(e)}")
        
        print(f"Completed checking {checked_count}/{len(links)} links")