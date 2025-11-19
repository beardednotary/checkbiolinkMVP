import requests

BASE_URL = "http://localhost:5000"

# Create a session to maintain cookies
session = requests.Session()

# 1. Register a user
print("=== Registering User ===")
response = session.post(
    f"{BASE_URL}/api/register",
    json={
        "email": "mail@checkbiolink.com",
        "password": "testpass123"
    }
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}\n")

# 2. Add a link to monitor
print("=== Adding Link ===")
response = session.post(
    f"{BASE_URL}/api/links",
    json={
        "url": "https://violetrend.com",
        "name": "VioleTrend Website"
    }
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}\n")

# 3. Get all links
print("=== Getting All Links ===")
response = session.get(f"{BASE_URL}/api/links")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}\n")

# 4. Add another link
print("=== Adding Second Link ===")
response = session.post(
    f"{BASE_URL}/api/links",
    json={
        "url": "https://cleanproteinlist.com",
        "name": "Clean Protein List Website"
    }
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}\n")

# 5. Get all links again
print("=== Getting All Links (Updated) ===")
response = session.get(f"{BASE_URL}/api/links")
print(f"Status: {response.status_code}")
links = response.json()
print(f"Response: {links}\n")

# 6. Manual check on first link
if links.get('links'):
    first_link_id = links['links'][0]['id']
    print(f"=== Manual Check on Link {first_link_id} ===")
    response = session.post(f"{BASE_URL}/api/links/{first_link_id}/check")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    
    # 7. Get history for that link
    print(f"=== Getting History for Link {first_link_id} ===")
    response = session.get(f"{BASE_URL}/api/links/{first_link_id}/history")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")