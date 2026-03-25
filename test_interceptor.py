import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__name__))))

from src.api import ApiClient, AuthenticationRequiredError
from src.services.auth_service import AuthService
from src.services.activity_service import ActivityService

def test_architecture():
    print("--- testing API Interceptor Architecture ---")
    
    # 1. Initialize API Client
    # Mocking endpoint for safe testing without hitting live servers during scratch test
    api_client = ApiClient(base_url="https://httpbin.org") 
    
    # 2. Initialize Auth Service (wires up the interceptor automatically)
    auth_service = AuthService(api_client)
    
    # 3. Initialize Activity Service (No longer needs auth_service!)
    activity_service = ActivityService(api_client)
    
    print("\nTest 1: Fetching activities without logging in (Should FAIL)")
    print("Calling activity_service.get_activities()...")
    try:
        activity_service.get_activities()
        print("FAIL: Request succeeded unexpectedly!")
    except AuthenticationRequiredError as e:
        print(f"SUCCESS: Caught expected Error: {e}")
    except Exception as e:
        print(f"FAIL: Caught unexpected error: {e}")

if __name__ == "__main__":
    test_architecture()
