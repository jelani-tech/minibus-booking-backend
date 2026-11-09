import unittest
from tests.base import BackendApiTestCase


class HealthAndSecurityHeadersTest(BackendApiTestCase):

    def test_health_returns_database_connected(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("database"), "connected")

    def test_security_headers_present_on_responses(self):
        response = self.client.get("/health")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("geolocation=()", response.headers.get("Permissions-Policy", ""))
        self.assertIn("app;dur=", response.headers.get("Server-Timing", ""))

    def test_api_routes_also_contain_security_headers(self):
        response = self.client.get("/api/trips")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")


if __name__ == "__main__":
    unittest.main()
