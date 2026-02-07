import requests
import os
import sys

BASE_URL = os.environ.get("CHECKBIOLINK_URL", "https://checkbiolink-mvp.onrender.com")

EMAIL = os.environ.get("CHECKBIOLINK_ADMIN_EMAIL")
PASSWORD = os.environ.get("CHECKBIOLINK_ADMIN_PASSWORD")

if not EMAIL or not PASSWORD:
    print("Set CHECKBIOLINK_ADMIN_EMAIL and CHECKBIOLINK_ADMIN_PASSWORD env vars first.")
    sys.exit(1)

session = requests.Session()

print("=== Setting Up Production CheckBioLink ===\n")

# 1. Register your account
print("1. Registering account...")
response = session.post(
    f"{BASE_URL}/api/register",
    json={"email": EMAIL, "password": PASSWORD}
)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}\n")

if response.status_code != 201:
    print("Registration failed. User might already exist. Trying to login...\n")
    response = session.post(
        f"{BASE_URL}/api/login",
        json={"email": EMAIL, "password": PASSWORD}
    )
    print(f"Login Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

# 2. Add your important links
links_to_monitor = [
    {"url": "https://violetrend.com", "name": "VioleTrend"},
    {"url": "https://checkbiolink.com", "name": "CheckBioLink Landing"},
    {"url": "https://cleanproteinlist.com", "name": "Clean Protein List"}
]

for link_data in links_to_monitor:
    print(f"Adding link: {link_data['name']}...")
    response = session.post(
        f"{BASE_URL}/api/links",
        json=link_data
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

# 3. Get all links to verify
print("=== Your Monitored Links ===")
response = session.get(f"{BASE_URL}/api/links")
if response.status_code == 200:
    links = response.json()['links']
    for link in links:
        status_icon = "[UP]" if link['status'] == 'up' else "[DOWN]" if link['status'] == 'down' else "[...]"
        print(f"{status_icon} {link['name']}: {link['url']} - Status: {link['status']}")
else:
    print(f"Error: {response.status_code}")

print("\n=== Setup Complete! ===")
print("Your links are now being monitored 24/7!")
print("You'll receive email alerts if any links go down.")
