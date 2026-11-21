"""Persist the logged-in session's cookies in the OS keyring.

Lets the GUI and the CLI share one server-side session instead of each logging
in separately. Stored per server host. Never raises: if the keyring is
unavailable, callers simply fall back to logging in as before.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import keyring

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self, service_name: str = "work-tracker"):
        self.service_name = service_name

    @staticmethod
    def _key(base_url: str) -> str:
        return f"session:{urlparse(base_url).netloc or base_url}"

    def load(self, base_url: str) -> Optional[List[Dict[str, Any]]]:
        """Return the saved cookies for this server, or None."""
        try:
            raw = keyring.get_password(self.service_name, self._key(base_url))
            cookies = json.loads(raw) if raw else None
            return cookies if isinstance(cookies, list) else None
        except Exception as exc:  # noqa: BLE001 - keyring backends raise many types
            logger.warning("Could not load saved session: %s", exc)
            return None

    def save(self, base_url: str, cookies: List[Dict[str, Any]]) -> bool:
        try:
            keyring.set_password(self.service_name, self._key(base_url), json.dumps(cookies))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not save session: %s", exc)
            return False

    def clear(self, base_url: str) -> None:
        try:
            keyring.delete_password(self.service_name, self._key(base_url))
        except keyring.errors.PasswordDeleteError:
            pass  # nothing stored
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not clear saved session: %s", exc)
