import requests

BASE = "https://api.example.com"


def get_user(user_id):
    r = requests.get(f"{BASE}/v1/users/{user_id}")
    return r.json()


def user_email(user_id):
    user = get_user(user_id)
    return user["email_address"]
