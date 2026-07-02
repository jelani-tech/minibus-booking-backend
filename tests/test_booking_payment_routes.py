from unittest.mock import patch
from uuid import uuid4

from tests.base import BackendApiTestCase


TEST_CUSTOMER_ID = "88888888-8888-8888-8888-888888888888"
TEST_AUTH_USER_ID = "99999999-9999-9999-9999-999999999999"
TEST_PASSWORD_HASH = "$2b$12$.MFBQ8RIgpwJyWHscoQ5vuFJ7Dgcaf36QbfbXeRbuInB9yhoGQtrW"


class BookingPaymentRoutesTest(BackendApiTestCase):
    def setUp(self):
        from models.public import db

        with self.app.app_context():
            db.session.execute(
                db.text(
                    """
                    delete from public.payments
                    where customer_id = cast(:customer_id as uuid)
                    """
                ),
                {"customer_id": TEST_CUSTOMER_ID},
            )
            db.session.execute(
                db.text(
                    """
                    delete from public.bookings
                    where customer_id = cast(:customer_id as uuid)
                    """
                ),
                {"customer_id": TEST_CUSTOMER_ID},
            )
            db.session.execute(
                db.text(
                    """
                    update public.trips
                    set capacity_booked = 0,
                        capacity_available = capacity_total - capacity_blocked
                    """
                )
            )
            db.session.execute(
                db.text(
                    """
                    insert into auth.users (id, phone, encrypted_password)
                    values (
                        cast(:auth_user_id as uuid),
                        :phone,
                        :encrypted_password
                    )
                    on conflict (phone) do update
                    set encrypted_password = excluded.encrypted_password
                    """
                ),
                {
                    "auth_user_id": TEST_AUTH_USER_ID,
                    "phone": "+2250100000003",
                    "encrypted_password": TEST_PASSWORD_HASH,
                },
            )
            db.session.execute(
                db.text(
                    """
                    update public.customers
                    set auth_user_id = cast(:auth_user_id as uuid),
                        email = null
                    where id = cast(:customer_id as uuid)
                    """
                ),
                {
                    "auth_user_id": TEST_AUTH_USER_ID,
                    "customer_id": TEST_CUSTOMER_ID,
                },
            )
            db.session.commit()

    def login(self):
        response = self.client.post(
            "/api/auth/login",
            json={
                "phone": "+2250100000003",
                "password": "dev-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["access_token"]

    def auth_headers(self):
        return {"Authorization": f"Bearer {self.login()}"}

    def first_trip_id(self):
        response = self.client.get("/api/trips")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["trips"][0]["id"]

    def create_booking(self):
        response = self.client.post(
            "/api/bookings",
            headers=self.auth_headers(),
            json={
                "trip_id": self.first_trip_id(),
                "number_of_seats": 1,
                "passenger_name": "Jean Client",
                "passenger_phone": "+2250100000003",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["booking"], response.request.headers

    def test_login_returns_customer_uuid(self):
        response = self.client.post(
            "/api/auth/login",
            json={
                "phone": "+2250100000003",
                "password": "dev-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("access_token", payload)
        self.assertEqual(payload["user"]["phone"], "+2250100000003")
        self.assertIn("-", payload["user"]["id"])

    def test_create_and_list_booking(self):
        headers = self.auth_headers()
        create_response = self.client.post(
            "/api/bookings",
            headers=headers,
            json={
                "trip_id": self.first_trip_id(),
                "number_of_seats": 1,
                "passenger_name": "Jean Client",
                "passenger_phone": "+2250100000003",
            },
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertIn("ticket_reference", create_response.get_json()["booking"])
        self.assertIn("qr_payload", create_response.get_json()["booking"])

        list_response = self.client.get("/api/bookings", headers=headers)

        self.assertEqual(list_response.status_code, 200)
        bookings = list_response.get_json()["bookings"]
        self.assertGreaterEqual(len(bookings), 1)
        self.assertIn("trip", bookings[0])

    def test_validate_ticket_by_reference(self):
        headers = self.auth_headers()
        create_response = self.client.post(
            "/api/bookings",
            headers=headers,
            json={
                "trip_id": self.first_trip_id(),
                "number_of_seats": 1,
                "passenger_name": "Jean Client",
                "passenger_phone": "+2250100000003",
            },
        )
        booking = create_response.get_json()["booking"]

        response = self.client.get(
            f"/api/bookings/ticket/{booking['ticket_reference']}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["booking"]["id"], booking["id"])

    def set_customer_email(self, email):
        from models.public import db

        with self.app.app_context():
            db.session.execute(
                db.text(
                    """
                    update public.customers
                    set email = :email
                    where id = cast(:customer_id as uuid)
                    """
                ),
                {"email": email, "customer_id": TEST_CUSTOMER_ID},
            )
            db.session.commit()

    def initiate_payment(self, headers, payload):
        with patch("routes.payment.PaystackService") as mock_service:
            mock_service.return_value.initialize_payment.return_value = {
                "authorization_url": "https://paystack.local/redirect",
                "access_code": "access-code",
                "reference": f"ref-{uuid4()}",
                "status": "pending",
            }
            response = self.client.post(
                "/api/payments/initiate",
                headers=headers,
                json=payload,
            )
        return response, mock_service.return_value.initialize_payment

    def fallback_payment_email(self):
        domain = self.app.config["PAYMENT_EMAIL_DOMAIN"]
        return f"client-{TEST_CUSTOMER_ID}@{domain}"

    def test_initiate_payment_with_provided_email(self):
        headers = self.auth_headers()
        booking_id = self.create_booking()[0]["id"]

        response, mock_initialize = self.initiate_payment(
            headers,
            {
                "booking_id": booking_id,
                "payment_email": "client@example.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("transaction_id", payload)
        self.assertEqual(payload["payment"]["booking_id"], booking_id)
        self.assertEqual(
            mock_initialize.call_args.kwargs["email"], "client@example.com"
        )

    def test_initiate_payment_without_email_uses_account_email(self):
        self.set_customer_email("jean.client@example.com")
        headers = self.auth_headers()
        booking_id = self.create_booking()[0]["id"]

        response, mock_initialize = self.initiate_payment(
            headers,
            {"booking_id": booking_id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            mock_initialize.call_args.kwargs["email"], "jean.client@example.com"
        )

    def test_initiate_payment_without_any_email_generates_stable_address(self):
        headers = self.auth_headers()
        booking_id = self.create_booking()[0]["id"]

        first_response, first_initialize = self.initiate_payment(
            headers,
            {"booking_id": booking_id},
        )
        second_response, second_initialize = self.initiate_payment(
            headers,
            {"booking_id": booking_id},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_email = first_initialize.call_args.kwargs["email"]
        second_email = second_initialize.call_args.kwargs["email"]
        self.assertEqual(first_email, self.fallback_payment_email())
        self.assertEqual(first_email, second_email)

    def test_initiate_payment_ignores_placeholder_email(self):
        headers = self.auth_headers()
        booking_id = self.create_booking()[0]["id"]

        response, mock_initialize = self.initiate_payment(
            headers,
            {
                "booking_id": booking_id,
                "payment_email": "email@email.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            mock_initialize.call_args.kwargs["email"], self.fallback_payment_email()
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
