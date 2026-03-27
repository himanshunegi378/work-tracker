import keyring
from typing import Dict, Optional

class CredentialStorage:
    """Persist remembered login credentials in the system keychain."""

    def __init__(self, service_name: str = "work-tracker"):
        """Initialize with the service name used for keyring entries."""
        self.service_name = service_name
        self._username_key = "saved_username"
    
    def save_credentials(self, credentials: Dict[str, str]) -> bool:
        """Store the username and password in the system keychain."""
        try:
            username = credentials.get("username")
            password = credentials.get("password")
            
            if not username or not password:
                return False
                
            # Store the username under a static key so we can find it later
            keyring.set_password(self.service_name, self._username_key, username)
            # Store the password using the username as the key
            keyring.set_password(self.service_name, username, password)
            
            return True
        except Exception as e:
            print(f"Error saving credentials to keyring: {e}")
            return False

    def load_credentials(self) -> Optional[Dict[str, str]]:
        """Retrieve saved credentials from the system keychain."""
        try:
            username = keyring.get_password(self.service_name, self._username_key)
            if not username:
                return None
                
            password = keyring.get_password(self.service_name, username)
            if password:
                return {"username": username, "password": password}
            
            return None
        except Exception as e:
            print(f"Error loading credentials from keyring: {e}")
            return None
            
    def clear_credentials(self) -> bool:
        """Remove saved credentials from the system keychain."""
        try:
            username = keyring.get_password(self.service_name, self._username_key)
            if username:
                keyring.delete_password(self.service_name, username)
            
            keyring.delete_password(self.service_name, self._username_key)
            return True
        except Exception as e:
            print(f"Error clearing credentials from keyring: {e}")
            return False
