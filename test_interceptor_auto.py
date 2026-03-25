import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__name__))))

from src.api import ApiClient, AuthenticationRequiredError
from src.services.auth_service import AuthService
from src.services.activity_service import ActivityService

def test_architecture():
    print("--- testing API Interceptor Architecture ---")
    
    # Using httpbin.org to mock
    api_client = ApiClient(base_url="https://httpbin.org") 
    
    # Initialize Auth Service with auto-login credentials
    # It will attempt to post to /login if a request needs a session
    auth_service = AuthService(api_client, auto_login_credentials={"username": "testUser", "password": "testPassword"})
    activity_service = ActivityService(api_client)
    
    print("\nTest 2: Fetching activities without logging in, WITH auto-login credentials provided")
    print("Calling activity_service.get_activities()...")
    try:
        activity_service.get_activities()
        print("SUCCESS! Request completed (the mock server returns an empty list, but it didn't throw an Auth error).")
    except Exception as e:
        print(f"FAILED (or expectedly failed due to HttpBin not being Frappe): {e}")

if __name__ == "__main__":
    test_architecture()
