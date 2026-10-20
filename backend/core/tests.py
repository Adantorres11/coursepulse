from django.test import TestCase


class HealthEndpointTests(TestCase):
    def test_health_returns_ok(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "coursepulse-api"})


class CorsTests(TestCase):
    def test_allowed_origin_gets_cors_header(self):
        response = self.client.get("/api/health/", HTTP_ORIGIN="http://localhost:5173")
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost:5173")

    def test_unlisted_origin_gets_no_cors_header(self):
        response = self.client.get("/api/health/", HTTP_ORIGIN="http://evil.example.com")
        self.assertNotIn("Access-Control-Allow-Origin", response)
