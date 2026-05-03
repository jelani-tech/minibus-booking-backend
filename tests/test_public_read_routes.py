from tests.base import BackendApiTestCase


class PublicReadRoutesTest(BackendApiTestCase):
    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "healthy")

    def test_get_lines_returns_active_lines_with_stops(self):
        response = self.client.get("/api/lines/")

        self.assertEqual(response.status_code, 200)
        lines = response.get_json()
        self.assertGreaterEqual(len(lines), 1)

        line = lines[0]
        self.assertIn("id", line)
        self.assertIn("code", line)
        self.assertIn("origin_name", line)
        self.assertIn("destination_name", line)
        self.assertIn("stops", line)
        self.assertGreaterEqual(len(line["stops"]), 1)
        self.assertIn("name", line["stops"][0])

    def test_get_trips_returns_flutter_compatible_trip_payload(self):
        response = self.client.get("/api/trips")

        self.assertEqual(response.status_code, 200)
        trips = response.get_json()["trips"]
        self.assertGreaterEqual(len(trips), 1)

        trip = trips[0]
        self.assertIn("id", trip)
        self.assertIn("departure_city", trip)
        self.assertIn("arrival_city", trip)
        self.assertIn("departure_time", trip)
        self.assertIn("arrival_time", trip)
        self.assertIn("price", trip)
        self.assertIn("available_seats", trip)
        self.assertIn("vehicle_number", trip)
        self.assertIsInstance(trip["vehicle"], dict)
        self.assertIsInstance(trip["line"], dict)

    def test_get_trip_by_uuid(self):
        trips_response = self.client.get("/api/trips")
        trip_id = trips_response.get_json()["trips"][0]["id"]

        response = self.client.get(f"/api/trips/{trip_id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["trip"]["id"], trip_id)


if __name__ == "__main__":
    import unittest

    unittest.main()

