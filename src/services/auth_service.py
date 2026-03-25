import logging
import urllib.parse
from typing import Any, Dict, Optional

# Assuming ApiClient and ApiClientError are in src.api as created previously
from src.api import ApiClient, ApiClientError
from src.persistence.credential_storage import CredentialStorage

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    """Raised when an authentication operation fails."""
    pass

class AuthService:
    """Owns login state, session checks, and credential persistence."""
    
    def __init__(self, api_client: ApiClient, credential_storage: Optional[CredentialStorage] = None):
        """Configure auth endpoints and wire session recovery into the API client."""
        self.api_client = api_client
        self.storage = credential_storage or CredentialStorage()
        
        # Load auto-login credentials from storage
        self.auto_login_credentials = self.storage.load_credentials()
        self.login_endpoint = "/login"
        # Frappe default endpoint to check current logged-in user
        self.get_user_endpoint = "/api/method/frappe.auth.get_logged_user"
        # Preflight endpoint to initialize session cookies before login
        self.preflight_endpoint = "/"
        
        # Wire up the ApiClient interceptor so it knows how to ensure session state
        self.api_client.auth_provider = self.ensure_session
        # Ensure preflight is also public (not blocked by auth check)
        self.api_client.public_endpoints.add(self.preflight_endpoint)

    def ensure_session(self) -> bool:
        """Keep requests authenticated by reusing the session or auto-logging in."""
        if self.is_logged_in():
            return True
            
        # Attempt auto-login if credentials are available
        if self.auto_login_credentials:
            logger.info("Session inactive, attempting auto-login...")
            try:
                # Catch errors here to prevent recursive Auth errors crashing the app entirely
                return self.login(
                    self.auto_login_credentials.get("username", ""), 
                    self.auto_login_credentials.get("password", "")
                )
            except Exception as e:
                logger.error(f"Auto-login failed: {e}")
                return False
                
        return False

    def is_logged_in(self) -> bool:
        """Return whether the backend still recognizes the current session."""
        return self.getSession() is not None

    def login(self, username: str, password: str) -> bool:
        """Authenticate against Frappe and persist credentials for auto-login."""
        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-frappe-cmd": "login",
            "x-requested-with": "XMLHttpRequest"
        }
        
        # Form-urlencoded data mapping to the expected Frappe format
        data = {
            "cmd": "login",
            "usr": username,
            "pwd": password
        }

        try:
            # Preflight GET to initialize session cookies (e.g. csrf_token) required by Frappe
            # The fragment (#login) is browser-only and ignored by the server, so we hit root.
            logger.info("Performing preflight GET to initialize session cookies...")
            try:
                self.api_client.get(self.preflight_endpoint)
            except Exception as e:
                # A non-200 preflight is non-fatal; cookies may still be set.
                logger.warning(f"Preflight GET returned an error (non-fatal): {e}")

            # Explicitly format the data as an x-www-form-urlencoded string
            encoded_data = urllib.parse.urlencode(data)
            
            # Send the explicit string as data
            response = self.api_client.post(
                self.login_endpoint, 
                data=encoded_data, 
                headers=headers
            )
            
            # Additional check: Sometimes frappe returns 200 OK but with a message indicating failure
            is_success = False
            if response.status_code == 200:
                try:
                    if "message" in response.json():
                        is_success = True
                except ValueError:
                    is_success = True
            
            if is_success:
                # Save credentials for future auto-login and persist to storage
                self.auto_login_credentials = {"username": username, "password": password}
                if self.storage:
                    self.storage.save_credentials(self.auto_login_credentials)
                return True
                
            return False
            
        except ApiClientError as e:
            logger.error("Login request failed")
            raise AuthenticationError(f"Failed to log in: {str(e)}") from e

    def getSession(self) -> Optional[str]:
        """Return the logged-in username, or `None` when the session has expired."""
        try:
            # Making a request to an endpoint that requires authentication
            # Frappe automatically uses the cookies maintained by ApiClient's session
            response = self.api_client.get(self.get_user_endpoint)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("message") # Frappe returns {"message": "user@example.com"}
            return None
            
        except ApiClientError:
            # Request failed (e.g. 401 Unauthorized or 403 Forbidden), meaning no valid session
            logger.debug("No active session found during getSession().")
            return None

    def refreshSession(self) -> bool:
        """Ping an authenticated endpoint so active sessions stay warm."""
        # If we can successfully fetch the current user, the session is active and its timeout is naturally extended.
        current_user = self.getSession()
        
        if current_user:
            logger.info(f"Session refreshed successfully for user: {current_user}")
            return True
            
        logger.warning("Failed to refresh session: No active session.")
        return False

    def logout(self) -> None:
        """Clear local session cookies and forget the current authenticated state."""
        self.api_client.clear_cookies()
        logger.info("User logged out locally.")

    def get_saved_username(self) -> Optional[str]:
        """Expose the remembered username so the login form can prefill it."""
        if self.auto_login_credentials:
            return self.auto_login_credentials.get("username")
        return None

    def get_saved_password(self) -> Optional[str]:
        """Expose the remembered password so the login form can prefill it."""
        if self.auto_login_credentials:
            return self.auto_login_credentials.get("password")
        return None
        
    def clear_saved_credentials(self) -> None:
        """Remove persisted credentials and end any active local session."""
        self.auto_login_credentials = None
        if self.storage:
            self.storage.clear_credentials()
        self.logout()
