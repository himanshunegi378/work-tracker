import logging
import json
import urllib.parse
from typing import Any, Callable, Dict, Optional

import requests

logger = logging.getLogger(__name__)

class ApiClientError(Exception):
    """Base exception for API client errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None,
        response_json: Optional[Dict[str, Any]] = None,
        server_messages: Optional[list[str]] = None,
        exc_type: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.response_json = response_json
        self.server_messages = server_messages or []
        self.exc_type = exc_type

    @classmethod
    def from_response(
        cls,
        response: Optional[requests.Response],
        *,
        default_message: str,
    ) -> "ApiClientError":
        """Build an error that preserves structured details from an HTTP response."""
        status_code = response.status_code if response is not None else None
        response_text = None
        response_json = None
        server_messages: list[str] = []
        exc_type = None
        details: list[str] = []

        if response is not None:
            response_text = response.text
            try:
                payload = response.json()
            except ValueError:
                payload = None

            if isinstance(payload, dict):
                response_json = payload
                server_messages = cls._extract_server_messages(payload.get("_server_messages"))
                exc_type = cls._clean_text(payload.get("exc_type"))
                message = cls._clean_text(payload.get("message"))
                exception_summary = cls._summarize_exception(payload.get("exception"))

                if exc_type:
                    details.append(exc_type)
                if message:
                    details.append(message)
                details.extend(server_messages)
                if exception_summary and not details:
                    details.append(exception_summary)

        base_message = default_message
        if status_code is not None:
            base_message = f"{base_message} (HTTP {status_code})"
        if details:
            base_message = f"{base_message}: {' | '.join(cls._dedupe_preserve_order(details))}"

        return cls(
            base_message,
            status_code=status_code,
            response_text=response_text,
            response_json=response_json,
            server_messages=server_messages,
            exc_type=exc_type,
        )

    @staticmethod
    def _extract_server_messages(raw_messages: Any) -> list[str]:
        """Normalize Frappe's nested _server_messages payload into readable strings."""
        if not raw_messages:
            return []

        try:
            decoded = json.loads(raw_messages) if isinstance(raw_messages, str) else raw_messages
        except (TypeError, ValueError):
            return [str(raw_messages)]

        if not isinstance(decoded, list):
            decoded = [decoded]

        messages: list[str] = []
        for item in decoded:
            parsed = item
            if isinstance(item, str):
                try:
                    parsed = json.loads(item)
                except ValueError:
                    parsed = item

            if isinstance(parsed, dict):
                cleaned_message = ApiClientError._clean_text(parsed.get("message"))
                if cleaned_message:
                    messages.append(cleaned_message)
            elif parsed:
                messages.append(str(parsed))

        return messages

    @staticmethod
    def _summarize_exception(raw_exception: Any) -> Optional[str]:
        """Keep only the most relevant line from a server exception payload."""
        cleaned = ApiClientError._clean_text(raw_exception)
        if not cleaned:
            return None
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        return lines[-1] if lines else None

    @staticmethod
    def _clean_text(value: Any) -> Optional[str]:
        """Convert response text fragments into compact single-line strings."""
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return " ".join(text.split())

    @staticmethod
    def _dedupe_preserve_order(items: list[str]) -> list[str]:
        """Remove duplicate detail strings without changing their order."""
        deduped: list[str] = []
        seen = set()
        for item in items:
            if item in seen:
                continue
            deduped.append(item)
            seen.add(item)
        return deduped

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
            logger.error(
                "Request timeout for %s %s | request=%s",
                method,
                url,
                self._build_request_log_context(kwargs),
            )
            raise ApiClientError(f"Request timed out: {e}") from e
        except requests.exceptions.HTTPError as e:
            self._log_http_failure(
                method=method,
                url=url,
                request_kwargs=kwargs,
                response=e.response,
                error=e,
            )
            raise ApiClientError.from_response(
                e.response,
                default_message="Request failed",
            ) from e
        except requests.exceptions.RequestException as e:
            response = getattr(e, "response", None)
            if response is not None:
                self._log_http_failure(
                    method=method,
                    url=url,
                    request_kwargs=kwargs,
                    response=response,
                    error=e,
                )
            else:
                logger.error(
                    "Request failed for %s %s: %s | request=%s",
                    method,
                    url,
                    e,
                    self._build_request_log_context(kwargs),
                )
            if response is not None:
                raise ApiClientError.from_response(
                    response,
                    default_message="Request failed",
                ) from e
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

    def _log_http_failure(
        self,
        *,
        method: str,
        url: str,
        request_kwargs: Dict[str, Any],
        response: Optional[requests.Response],
        error: Exception,
    ) -> None:
        """Log a failed HTTP exchange with sanitized request and response details."""
        logger.error(
            "Request failed for %s %s: %s\nrequest=%s\nresponse=%s",
            method,
            url,
            error,
            self._format_log_value(self._build_request_log_context(request_kwargs)),
            self._format_log_value(self._build_response_log_context(response)),
        )

    def _build_request_log_context(self, request_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract safe request details for diagnostics."""
        context: Dict[str, Any] = {}

        for key in ("params", "data", "json"):
            if key in request_kwargs and request_kwargs[key] is not None:
                context[key] = self._sanitize_request_value(key, request_kwargs[key])

        headers = request_kwargs.get("headers")
        if headers:
            context["headers"] = self._sanitize_headers(headers)

        timeout = request_kwargs.get("timeout")
        if timeout is not None:
            context["timeout"] = timeout

        return context

    def _build_response_log_context(
        self,
        response: Optional[requests.Response],
    ) -> Dict[str, Any]:
        """Extract response details for diagnostics."""
        if response is None:
            return {}

        response_text = None
        try:
            response_text = response.text
        except Exception:
            response_text = None

        return {
            "status_code": response.status_code,
            "headers": self._sanitize_headers(dict(response.headers)),
            "body": self._sanitize_response_body(response_text),
        }

    def _sanitize_headers(self, headers: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive header values before logging."""
        redacted = {}
        sensitive_headers = {
            "authorization",
            "cookie",
            "set-cookie",
            "x-api-key",
            "x-auth-token",
        }
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                redacted[key] = "<redacted>"
            else:
                redacted[key] = self._truncate_for_logging(value)
        return redacted

    def _sanitize_for_logging(self, value: Any) -> Any:
        """Redact common secrets and trim large payloads before logging."""
        if isinstance(value, dict):
            sensitive_keys = {
                "password",
                "passwd",
                "token",
                "csrf_token",
                "sid",
                "cookie",
                "authorization",
            }
            sanitized = {}
            for key, item in value.items():
                if str(key).lower() in sensitive_keys:
                    sanitized[key] = "<redacted>"
                else:
                    sanitized[key] = self._sanitize_for_logging(item)
            return sanitized

        if isinstance(value, (list, tuple)):
            return [self._sanitize_for_logging(item) for item in value]

        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8", errors="replace")
            except Exception:
                value = repr(value)

        if isinstance(value, str):
            return self._truncate_for_logging(value)

        return value

    def _sanitize_request_value(self, key: str, value: Any) -> Any:
        """Decode common request payload formats before logging."""
        sanitized = self._sanitize_for_logging(value)
        if key == "data" and isinstance(value, str):
            decoded_form = self._decode_form_encoded_payload(value)
            if decoded_form is not None:
                return decoded_form
        return sanitized

    def _sanitize_response_body(self, value: Any) -> Any:
        """Pretty-print JSON response bodies when available."""
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except ValueError:
                return self._truncate_for_logging(value)
            return self._sanitize_for_logging(parsed)
        return self._sanitize_for_logging(value)

    def _decode_form_encoded_payload(self, data: str) -> Optional[Dict[str, Any]]:
        """Decode x-www-form-urlencoded payloads for readable logging."""
        try:
            parsed = urllib.parse.parse_qs(data, keep_blank_values=True)
        except Exception:
            return None

        if not parsed:
            return None

        decoded: Dict[str, Any] = {}
        for key, values in parsed.items():
            value: Any = values if len(values) != 1 else values[0]
            if key == "doc" and isinstance(value, str):
                try:
                    value = json.loads(value)
                except ValueError:
                    value = value
            decoded[key] = self._sanitize_for_logging(value)
        return decoded

    def _format_log_value(self, value: Any) -> str:
        """Render log context as readable JSON when possible."""
        try:
            return json.dumps(value, indent=2, sort_keys=True, default=str)
        except TypeError:
            return self._truncate_for_logging(value)

    def _truncate_for_logging(self, value: Any, limit: int = 4000) -> str:
        """Keep logged values readable and bounded."""
        text = str(value)
        if len(text) <= limit:
            return text
        return f"{text[:limit]}... [truncated {len(text) - limit} chars]"
