import logging
from typing import Any, Callable, Dict, Optional

import requests

logger = logging.getLogger(__name__)

class ApiClientError(Exception):
    """Base exception for API client errors."""
    pass

class AuthenticationRequiredError(ApiClientError):
    """Raised when an API request is made without a valid session."""
    pass

class ApiClient:
    """Wrap `requests.Session` with shared auth checks and consistent errors."""

    def __init__(self, base_url: str = "", default_timeout: int = 10):
        """Configure the base URL, timeout, and reusable HTTP session."""
        self.base_url = base_url.rstrip('/')
        self.default_timeout = default_timeout
        # Using Session to persist cookies and enable connection pooling (Keep-Alive)
        self.session = requests.Session()
        
        # Optional callback to verify authentication before firing requests
        self.auth_provider: Optional[Callable[[], bool]] = None
        
        # Endpoints that are allowed to bypass the auth_provider check
        self.public_endpoints = {
            "/login",
            "/api/method/frappe.auth.get_logged_user"
        }

    def _build_url(self, endpoint: str) -> str:
        """Constructs the full URL for the given endpoint."""
        if not endpoint.startswith(('http://', 'https://')):
            endpoint = endpoint.lstrip('/')
            if self.base_url:
                return f"{self.base_url}/{endpoint}"
        return endpoint

    def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> requests.Response:
        """Send one HTTP request after auth checks and normalize transport errors."""
        # Run the pre-flight auth check if configured, unless it's a public endpoint
        if self.auth_provider and endpoint not in self.public_endpoints:
            if not self.auth_provider():
                logger.warning(f"Blocked unauthenticated request to {endpoint}")
                raise AuthenticationRequiredError("User is not logged in. Request aborted.")

        url = self._build_url(endpoint)
        
        # Ensure a default timeout is always present
        kwargs.setdefault('timeout', self.default_timeout)

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout for {method} {url}")
            raise ApiClientError(f"Request timed out: {e}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {method} {url}: {e}")
            raise ApiClientError(f"Request failed: {e}") from e

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """Send a GET request through the shared session."""
        return self._request('GET', endpoint, params=params, **kwargs)

    def post(self, endpoint: str, data: Optional[Any] = None, json: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """Send a POST request through the shared session."""
        return self._request('POST', endpoint, data=data, json=json, **kwargs)

    def put(self, endpoint: str, data: Optional[Any] = None, json: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """Send a PUT request through the shared session."""
        return self._request('PUT', endpoint, data=data, json=json, **kwargs)

    def patch(self, endpoint: str, data: Optional[Any] = None, json: Optional[Dict[str, Any]] = None, **kwargs: Any) -> requests.Response:
        """Send a PATCH request through the shared session."""
        return self._request('PATCH', endpoint, data=data, json=json, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> requests.Response:
        """Send a DELETE request through the shared session."""
        return self._request('DELETE', endpoint, **kwargs)
    
    def get_cookies(self) -> Dict[str, str]:
        """Returns the current cookies stored in the session."""
        return requests.utils.dict_from_cookiejar(self.session.cookies)
        
    def clear_cookies(self) -> None:
        """Clears all session cookies."""
        self.session.cookies.clear()
        
    def close(self) -> None:
        """Closes the underlying session."""
        self.session.close()

    def __enter__(self):
        """Allows use as a context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensures the session is closed when exiting context."""
        self.close()
