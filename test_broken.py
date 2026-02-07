import requests

BASE_URL = "https://checkbiolink-mvp.onrender.com"
session = requests.Session()

# Login
session.post(
    f"{BASE_URL}/api/login",
    json={"email": "mail@checkbiolink.com", "password": "Vi0l3t09141236!@"}
)

# Add a broken link to test alerts
session.post(
    f"{BASE_URL}/api/links",
    json={"url": "https://this-will-definitely-fail-12345.com", "name": "Test Broken Link"}
)

print("Broken link added! Wait 10 minutes for the next cron check.")
print("You should receive an email alert when it's detected as down.")