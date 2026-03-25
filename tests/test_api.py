import os
import sys
import unittest
from unittest.mock import MagicMock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.api import ApiClient, ApiClientError


class TestApiClient(unittest.TestCase):
    def test_post_surfaces_frappe_server_messages_on_http_error(self):
        client = ApiClient(base_url="https://example.com")
        response = MagicMock()
        response.status_code = 417
        response.text = (
            '{"exc_type":"ValidationError","_server_messages":"['
            '\\"{\\\\\\"message\\\\\\": \\\\\\"Row 1: Activity Type is required\\\\\\"}\\"'
            ']"}'
        )
        response.json.return_value = {
            "exc_type": "ValidationError",
            "_server_messages": '["{\\"message\\": \\"Row 1: Activity Type is required\\"}"]',
        }

        http_error = requests.exceptions.HTTPError("417 Client Error", response=response)
        client.session.request = MagicMock(return_value=response)
        response.raise_for_status.side_effect = http_error

        with self.assertRaises(ApiClientError) as ctx:
            client.post("/api/method/frappe.desk.form.save.savedocs", data="doc={}")

        self.assertEqual(ctx.exception.status_code, 417)
        self.assertEqual(
            ctx.exception.server_messages,
            ["Row 1: Activity Type is required"],
        )
        self.assertIn("HTTP 417", str(ctx.exception))
        self.assertIn("ValidationError", str(ctx.exception))
        self.assertIn("Activity Type is required", str(ctx.exception))

    def test_post_logs_request_payload_and_response_body_on_http_error(self):
        client = ApiClient(base_url="https://example.com")
        response = MagicMock()
        response.status_code = 417
        response.text = '{"exc_type":"ValidationError","message":"boom"}'
        response.headers = {
            "Content-Type": "application/json",
            "Set-Cookie": "secret-cookie",
        }
        response.json.return_value = {
            "exc_type": "ValidationError",
            "message": "boom",
        }

        http_error = requests.exceptions.HTTPError("417 Client Error", response=response)
        client.session.request = MagicMock(return_value=response)
        response.raise_for_status.side_effect = http_error

        with self.assertLogs("src.api", level="ERROR") as captured:
            with self.assertRaises(ApiClientError):
                client.post(
                    "/api/method/frappe.desk.form.save.savedocs",
                    data="doc={\"secret\":\"value\"}",
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Cookie": "sid=123",
                    },
                )

        combined = "\n".join(captured.output)
        self.assertIn("request=", combined)
        self.assertIn('"data"', combined)
        self.assertIn('"doc"', combined)
        self.assertIn('"secret": "value"', combined)
        self.assertIn("headers", combined)
        self.assertIn("<redacted>", combined)
        self.assertIn("response=", combined)
        self.assertIn('"status_code": 417', combined)
        self.assertIn('"body"', combined)
        self.assertIn("ValidationError", combined)


if __name__ == "__main__":
    unittest.main()
