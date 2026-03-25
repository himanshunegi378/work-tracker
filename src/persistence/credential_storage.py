import json
from typing import Dict, Optional
from pathlib import Path

class CredentialStorage:
    """Persist remembered login credentials for the auto-login flow."""

    def __init__(self, file_path: str = "data/credentials.json"):
        """Choose the backing file used to store saved credentials."""
        self.file_path = Path(file_path)
    
    def save_credentials(self, credentials: Dict[str, str]) -> bool:
        """Write the current username and password payload to disk."""
        try:
            # Ensure directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(credentials, f, indent=4)
            return True
        except IOError as e:
            print(f"Error saving credentials to {self.file_path}: {e}")
            return False

    def load_credentials(self) -> Optional[Dict[str, str]]:
        """Load saved credentials when the file exists and has the expected shape."""
        if not self.file_path.exists():
            return None
            
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'username' in data and 'password' in data:
                    return data
                return None
        except (json.JSONDecodeError, IOError):
            print(f"Error loading credentials from {self.file_path}")
            return None
            
    def clear_credentials(self) -> bool:
        """Delete any saved credential file from disk."""
        try:
            if self.file_path.exists():
                self.file_path.unlink()
            return True
        except IOError as e:
            print(f"Error clearing credentials from {self.file_path}: {e}")
            return False
