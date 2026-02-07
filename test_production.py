import requests

BASE_URL = "https://checkbiolink-mvp.onrender.com"

session = requests.Session()

print("=== Testing Production Deployment ===\n")

# 1. Register
print("1. Registering user...")
response = session.post(
    f"{BASE_URL}/api/register",
    json={
        "email": "mail@checkbiolink.com",
        "password": "testpass123"
    }
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}\n")

# 2. Add your first link
print("2. Adding VioleTrend link...")
response = session.post(
    f"{BASE_URL}/api/links",
    json={
        "url": "https://violetrend.com",
        "name": "VioleTrend"
    }
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}\n")

# 3. Add second link
print("3. Adding CheckBioLink landing page...")
response = session.post(
    f"{BASE_URL}/api/links",
    json={
        "url": "https://checkbiolink.com",
        "name": "CheckBioLink Landing Page"
    }
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}\n")

# 4. Get all links
print("4. Getting all links...")
response = session.get(f"{BASE_URL}/api/links")
print(f"Status: {response.status_code}")
links = response.json()
print(f"Links: {links}\n")

# 5. Manual check
if links.get('links'):
    link_id = links['links'][0]['id']
    print(f"5. Manual check on link {link_id}...")
    response = session.post(f"{BASE_URL}/api/links/{link_id}/check")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

print("=== All tests completed! ===")