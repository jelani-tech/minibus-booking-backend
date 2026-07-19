import hashlib
import hmac
import json
from unittest.mock import patch
from uuid import uuid4

from tests.base import BackendApiTestCase


TEST_CUSTOMER_ID = "88888888-8888-8888-8888-888888888888"
TEST_AUTH_USER_ID = "99999999-9999-9999-9999-999999999999"
TEST_PASSWORD_HASH = "$2b$12$.MFBQ8RIgpwJyWHscoQ5vuFJ7Dgcaf36QbfbXeRbuInB9yhoGQtrW"
WEBHOOK_TEST_SECRET = "sk_test_webhook_secret"
JEKO_WEBHOOK_TEST_SECRET = "jeko_test_webhook_secret"
JEKO_TEST_PUBLIC_BASE_URL = "https://api.test.local"


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

    def trip_stop_ids(self, trip_id):
        """Premier et dernier arrêt de la ligne du trip (pickup/dropoff)."""
        from models.public import db

        with self.app.app_context():
            rows = db.session.execute(
                db.text(
                    """
                    select ls.stop_id
                    from public.line_stops ls
                    join public.trips t on t.line_id = ls.line_id
                    where t.id = cast(:trip_id as uuid)
                    order by ls.stop_order
                    """
                ),
                {"trip_id": trip_id},
            ).scalars().all()
        self.assertGreaterEqual(len(rows), 2)
        return str(rows[0]), str(rows[-1])

    def create_booking(self):
        trip_id = self.first_trip_id()
        pickup_stop_id, dropoff_stop_id = self.trip_stop_ids(trip_id)
        response = self.client.post(
            "/api/bookings",
            headers=self.auth_headers(),
            json={
                "trip_id": trip_id,
                "number_of_seats": 1,
                "passenger_name": "Jean Client",
                "passenger_phone": "+2250100000003",
                "pickup_stop_id": pickup_stop_id,
                "dropoff_stop_id": dropoff_stop_id,
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
        trip_id = self.first_trip_id()
        pickup_stop_id, dropoff_stop_id = self.trip_stop_ids(trip_id)
        create_response = self.client.post(
            "/api/bookings",
            headers=headers,
            json={
                "trip_id": trip_id,
                "number_of_seats": 1,
                "passenger_name": "Jean Client",
                "passenger_phone": "+2250100000003",
                "pickup_stop_id": pickup_stop_id,
                "dropoff_stop_id": dropoff_stop_id,
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
        booking = self.create_booking()[0]

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

    # ------------------------------------------------------------------
    # Callback Paystack (/api/payments/callback) et webhook
    # ------------------------------------------------------------------

    def initiate_pending_payment(self):
        headers = self.auth_headers()
        booking = self.create_booking()[0]
        response, _ = self.initiate_payment(
            headers,
            {"booking_id": booking["id"], "payment_email": "client@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        payment = response.get_json()["payment"]
        self.assertEqual(payment["status"], "pending")
        return headers, booking, payment

    def paystack_transaction_data(self, payment, status="success", amount=None, currency="XOF"):
        return {
            "id": 4242,
            "reference": payment["provider_reference"],
            "status": status,
            "amount": (
                amount
                if amount is not None
                else int(round(float(payment["amount"]) * 100))
            ),
            "currency": currency,
        }

    def call_payment_callback(self, reference, verify_data):
        with patch("routes.payment.PaystackService") as mock_service:
            mock_service.return_value.verify_payment.return_value = verify_data
            response = self.client.get(
                "/api/payments/callback",
                query_string={"trxref": reference, "reference": reference},
            )
        return response

    def post_payment_webhook(self, data, event="charge.success", signature=None):
        """signature: None = signature valide, False = header absent, str = valeur brute."""
        self.app.config["PAYSTACK_SECRET_KEY"] = WEBHOOK_TEST_SECRET
        body = json.dumps({"event": event, "data": data}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if signature is None:
            signature = hmac.new(
                WEBHOOK_TEST_SECRET.encode("utf-8"), body, hashlib.sha512
            ).hexdigest()
        if signature is not False:
            headers["x-paystack-signature"] = signature
        return self.client.post("/api/payments/webhook", data=body, headers=headers)

    def payment_status_from_api(self, headers, booking_id):
        response = self.client.get(
            f"/api/payments/status/{booking_id}", headers=headers
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["payment"]

    def booking_row(self, booking_id):
        from models.public import db

        with self.app.app_context():
            row = db.session.execute(
                db.text(
                    """
                    select booking_status, payment_status
                    from public.bookings
                    where id = cast(:booking_id as uuid)
                    """
                ),
                {"booking_id": booking_id},
            ).mappings().first()
            return dict(row)

    def set_booking_status(self, booking_id, booking_status):
        from models.public import db

        with self.app.app_context():
            db.session.execute(
                db.text(
                    """
                    update public.bookings
                    set booking_status = :booking_status
                    where id = cast(:booking_id as uuid)
                    """
                ),
                {"booking_id": booking_id, "booking_status": booking_status},
            )
            db.session.commit()

    def payments_count(self, booking_id):
        from models.public import db

        with self.app.app_context():
            return db.session.execute(
                db.text(
                    """
                    select count(*)
                    from public.payments
                    where booking_id = cast(:booking_id as uuid)
                    """
                ),
                {"booking_id": booking_id},
            ).scalar()

    def test_callback_success_confirms_payment_and_booking(self):
        headers, booking, payment = self.initiate_pending_payment()

        response = self.call_payment_callback(
            payment["provider_reference"],
            self.paystack_transaction_data(payment),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        api_payment = self.payment_status_from_api(headers, booking["id"])
        self.assertEqual(api_payment["status"], "success")
        self.assertIsNotNone(api_payment["transaction_id"])
        booking_row = self.booking_row(booking["id"])
        self.assertEqual(booking_row["booking_status"], "confirmed")
        self.assertEqual(booking_row["payment_status"], "paid")

    def test_callback_unknown_reference_returns_200_without_changes(self):
        headers, booking, payment = self.initiate_pending_payment()
        verify_data = self.paystack_transaction_data(payment)
        verify_data["reference"] = "ref-inconnue"

        response = self.call_payment_callback("ref-inconnue", verify_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "pending"
        )
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "pending")

    def test_callback_verify_failure_marks_payment_failed(self):
        for provider_status in ("failed", "abandoned"):
            with self.subTest(provider_status=provider_status):
                headers, booking, payment = self.initiate_pending_payment()

                response = self.call_payment_callback(
                    payment["provider_reference"],
                    self.paystack_transaction_data(payment, status=provider_status),
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    self.payment_status_from_api(headers, booking["id"])["status"],
                    "failed",
                )
                booking_row = self.booking_row(booking["id"])
                self.assertEqual(booking_row["booking_status"], "pending")
                self.assertEqual(booking_row["payment_status"], "failed")

    def test_callback_amount_mismatch_does_not_confirm(self):
        headers, booking, payment = self.initiate_pending_payment()

        response = self.call_payment_callback(
            payment["provider_reference"],
            self.paystack_transaction_data(payment, amount=1),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "pending"
        )
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "pending")

    def test_webhook_rejects_missing_or_invalid_signature(self):
        headers, booking, payment = self.initiate_pending_payment()
        data = self.paystack_transaction_data(payment)

        missing = self.post_payment_webhook(data, signature=False)
        invalid = self.post_payment_webhook(data, signature="0" * 128)

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "pending"
        )
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "pending")

    def test_webhook_unknown_reference_returns_200(self):
        response = self.post_payment_webhook(
            {
                "reference": "ref-inconnue",
                "status": "success",
                "amount": 100,
                "currency": "XOF",
            }
        )

        self.assertEqual(response.status_code, 200)

    def test_callback_then_webhook_failure_never_downgrades_success(self):
        headers, booking, payment = self.initiate_pending_payment()
        self.call_payment_callback(
            payment["provider_reference"],
            self.paystack_transaction_data(payment),
        )

        webhook_response = self.post_payment_webhook(
            self.paystack_transaction_data(payment, status="failed"),
            event="charge.failed",
        )

        self.assertEqual(webhook_response.status_code, 200)
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "success"
        )
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "confirmed")

    def test_reinitiate_payment_reuses_pending_row_and_follows_new_reference(self):
        headers, booking, first_payment = self.initiate_pending_payment()

        response, _ = self.initiate_payment(
            headers,
            {"booking_id": booking["id"], "payment_email": "client@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        second_payment = response.get_json()["payment"]
        self.assertEqual(second_payment["id"], first_payment["id"])
        self.assertNotEqual(
            second_payment["provider_reference"], first_payment["provider_reference"]
        )
        self.assertEqual(self.payments_count(booking["id"]), 1)

        # Le paiement du booking suit la derniere reference emise
        self.call_payment_callback(
            second_payment["provider_reference"],
            self.paystack_transaction_data(second_payment),
        )
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "success"
        )

    def test_reinitiate_after_failure_resets_payment_to_pending(self):
        headers, booking, payment = self.initiate_pending_payment()
        self.call_payment_callback(
            payment["provider_reference"],
            self.paystack_transaction_data(payment, status="failed"),
        )
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "failed"
        )

        response, _ = self.initiate_payment(
            headers,
            {"booking_id": booking["id"], "payment_email": "client@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        new_payment = response.get_json()["payment"]
        self.assertEqual(new_payment["id"], payment["id"])
        self.assertEqual(new_payment["status"], "pending")
        self.assertEqual(self.payments_count(booking["id"]), 1)

    def test_late_event_does_not_touch_cancelled_booking(self):
        for provider_status in ("success", "failed"):
            with self.subTest(provider_status=provider_status):
                headers, booking, payment = self.initiate_pending_payment()
                self.set_booking_status(booking["id"], "cancelled")

                response = self.post_payment_webhook(
                    self.paystack_transaction_data(payment, status=provider_status),
                    event=(
                        "charge.success"
                        if provider_status == "success"
                        else "charge.failed"
                    ),
                )

                self.assertEqual(response.status_code, 200)
                # Le paiement est solde mais le booking annule reste annule
                expected_payment_status = (
                    "success" if provider_status == "success" else "failed"
                )
                self.assertEqual(
                    self.payment_status_from_api(headers, booking["id"])["status"],
                    expected_payment_status,
                )
                booking_row = self.booking_row(booking["id"])
                self.assertEqual(booking_row["booking_status"], "cancelled")
                self.assertEqual(booking_row["payment_status"], "pending")

    def test_webhook_then_callback_is_idempotent(self):
        headers, booking, payment = self.initiate_pending_payment()
        data = self.paystack_transaction_data(payment)

        webhook_response = self.post_payment_webhook(data)
        self.assertEqual(webhook_response.status_code, 200)
        first = self.payment_status_from_api(headers, booking["id"])
        self.assertEqual(first["status"], "success")

        callback_response = self.call_payment_callback(
            payment["provider_reference"], data
        )

        self.assertEqual(callback_response.status_code, 200)
        second = self.payment_status_from_api(headers, booking["id"])
        self.assertEqual(second["status"], "success")
        # Aucune re-ecriture lors de la seconde livraison
        self.assertEqual(second["updated_at"], first["updated_at"])
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "confirmed")

    # ------------------------------------------------------------------
    # JEKO : initiation, webhook (/api/payments/jeko/webhook) et callback
    # ------------------------------------------------------------------

    def use_jeko_provider(self):
        original_provider = self.app.config.get("PAYMENT_PROVIDER")
        original_base_url = self.app.config.get("PAYMENT_PUBLIC_BASE_URL")

        def restore():
            self.app.config["PAYMENT_PROVIDER"] = original_provider
            self.app.config["PAYMENT_PUBLIC_BASE_URL"] = original_base_url

        self.addCleanup(restore)
        self.app.config["PAYMENT_PROVIDER"] = "jeko"
        self.app.config["PAYMENT_PUBLIC_BASE_URL"] = JEKO_TEST_PUBLIC_BASE_URL

    def initiate_jeko_payment(self, headers, payload):
        self.use_jeko_provider()
        with patch("routes.payment.JekoService") as mock_service:
            mock_service.return_value.initialize_payment.return_value = {
                "payment_url": "https://pay.jeko.local/redirect",
                "provider_payment_id": str(uuid4()),
                "status": "pending",
                "raw": {"redirectUrl": "https://pay.jeko.local/redirect"},
            }
            response = self.client.post(
                "/api/payments/initiate",
                headers=headers,
                json=payload,
            )
        return response, mock_service.return_value.initialize_payment

    def initiate_jeko_pending_payment(self):
        headers = self.auth_headers()
        booking = self.create_booking()[0]
        response, _ = self.initiate_jeko_payment(
            headers,
            {"booking_id": booking["id"], "payment_method": "wave"},
        )
        self.assertEqual(response.status_code, 200)
        payment = response.get_json()["payment"]
        self.assertEqual(payment["status"], "pending")
        return headers, booking, payment

    def jeko_webhook_data(self, payment, status="success", amount=None, currency="XOF"):
        return {
            "id": "txn_1234567890",
            "status": status,
            "amount": {
                "amount": (
                    amount
                    if amount is not None
                    else int(round(float(payment["amount"]) * 100))
                ),
                "currency": currency,
            },
            "fees": {"amount": 150, "currency": currency},
            "transactionType": "payment",
            "transactionDetails": {
                "id": "pr_abc123",
                "reference": payment["provider_reference"],
            },
        }

    def post_jeko_webhook(self, data, signature=None):
        """signature: None = signature valide, False = header absent, str = valeur brute."""
        self.app.config["JEKO_WEBHOOK_SECRET"] = JEKO_WEBHOOK_TEST_SECRET
        body = json.dumps(data).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if signature is None:
            signature = hmac.new(
                JEKO_WEBHOOK_TEST_SECRET.encode("utf-8"), body, hashlib.sha256
            ).hexdigest()
        if signature is not False:
            headers["Jeko-Signature"] = signature
        return self.client.post("/api/payments/jeko/webhook", data=body, headers=headers)

    def jeko_verification_data(self, payment, status="success", amount=None, currency="XOF"):
        return {
            "status": status,
            "amount": (
                amount
                if amount is not None
                else int(round(float(payment["amount"]) * 100))
            ),
            "currency": currency,
            "reference": payment["provider_reference"],
            "provider_payment_id": "pr_abc123",
            "raw": {},
        }

    def call_jeko_callback(self, reference, verify_data=None):
        with patch("routes.payment.JekoService") as mock_service:
            if verify_data is not None:
                mock_service.return_value.verify_payment.return_value = verify_data
            response = self.client.get(
                "/api/payments/callback",
                query_string={"provider": "jeko", "reference": reference},
            )
        return response, mock_service.return_value.verify_payment

    def test_initiate_jeko_payment(self):
        headers = self.auth_headers()
        booking = self.create_booking()[0]

        response, mock_initialize = self.initiate_jeko_payment(
            headers,
            {"booking_id": booking["id"], "payment_method": "wave"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        payment = payload["payment"]
        self.assertEqual(payment["provider"], "jeko")
        self.assertEqual(payload["payment_url"], "https://pay.jeko.local/redirect")
        self.assertTrue(payment["provider_reference"].startswith("JEKO-"))

        call_kwargs = mock_initialize.call_args.kwargs
        self.assertEqual(
            call_kwargs["amount_cents"],
            int(round(float(payment["amount"]) * 100)),
        )
        self.assertEqual(call_kwargs["payment_method"], "wave")
        expected_callback = (
            f"{JEKO_TEST_PUBLIC_BASE_URL}/api/payments/callback"
            f"?provider=jeko&reference={payment['provider_reference']}"
        )
        self.assertEqual(call_kwargs["success_url"], expected_callback)
        self.assertEqual(call_kwargs["error_url"], expected_callback)

    def test_initiate_jeko_payment_requires_valid_payment_method(self):
        headers = self.auth_headers()
        booking = self.create_booking()[0]

        for payload in (
            {"booking_id": booking["id"]},
            {"booking_id": booking["id"], "payment_method": "paypal"},
        ):
            with self.subTest(payload=payload):
                response, mock_initialize = self.initiate_jeko_payment(headers, payload)

                self.assertEqual(response.status_code, 400)
                self.assertIn("payment_method", response.get_json()["error"])
                mock_initialize.assert_not_called()
        self.assertEqual(self.payments_count(booking["id"]), 0)

    def test_initiate_with_paystack_provider_ignores_payment_method(self):
        headers = self.auth_headers()
        booking = self.create_booking()[0]

        response, mock_initialize = self.initiate_payment(
            headers,
            {
                "booking_id": booking["id"],
                "payment_email": "client@example.com",
                "payment_method": "wave",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["payment"]["provider"], "paystack")
        self.assertNotIn("payment_method", mock_initialize.call_args.kwargs)

    def test_jeko_webhook_success_confirms_payment_and_booking(self):
        headers, booking, payment = self.initiate_jeko_pending_payment()

        response = self.post_jeko_webhook(self.jeko_webhook_data(payment))

        self.assertEqual(response.status_code, 200)
        api_payment = self.payment_status_from_api(headers, booking["id"])
        self.assertEqual(api_payment["status"], "success")
        booking_row = self.booking_row(booking["id"])
        self.assertEqual(booking_row["booking_status"], "confirmed")
        self.assertEqual(booking_row["payment_status"], "paid")

    def test_jeko_webhook_error_marks_payment_failed(self):
        headers, booking, payment = self.initiate_jeko_pending_payment()

        response = self.post_jeko_webhook(
            self.jeko_webhook_data(payment, status="error")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "failed"
        )
        booking_row = self.booking_row(booking["id"])
        self.assertEqual(booking_row["booking_status"], "pending")
        self.assertEqual(booking_row["payment_status"], "failed")

    def test_jeko_webhook_rejects_missing_or_invalid_signature(self):
        headers, booking, payment = self.initiate_jeko_pending_payment()
        data = self.jeko_webhook_data(payment)

        missing = self.post_jeko_webhook(data, signature=False)
        invalid = self.post_jeko_webhook(data, signature="0" * 64)

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "pending"
        )
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "pending")

    def test_jeko_webhook_amount_mismatch_does_not_confirm(self):
        headers, booking, payment = self.initiate_jeko_pending_payment()

        response = self.post_jeko_webhook(self.jeko_webhook_data(payment, amount=1))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "pending"
        )
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "pending")

    def test_jeko_callback_verifies_by_provider_payment_id_and_settles(self):
        headers, booking, payment = self.initiate_jeko_pending_payment()

        response, mock_verify = self.call_jeko_callback(
            payment["provider_reference"],
            self.jeko_verification_data(payment),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        # Verification par l'id JEKO stocke a l'initiation, pas par la reference
        called_id = mock_verify.call_args.args[0]
        self.assertNotEqual(called_id, payment["provider_reference"])
        api_payment = self.payment_status_from_api(headers, booking["id"])
        self.assertEqual(api_payment["status"], "success")
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "confirmed")

    def test_jeko_callback_after_webhook_skips_verification(self):
        headers, booking, payment = self.initiate_jeko_pending_payment()
        webhook_response = self.post_jeko_webhook(self.jeko_webhook_data(payment))
        self.assertEqual(webhook_response.status_code, 200)

        response, mock_verify = self.call_jeko_callback(payment["provider_reference"])

        self.assertEqual(response.status_code, 200)
        mock_verify.assert_not_called()
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "success"
        )

    def test_paystack_webhook_still_settles_when_jeko_is_active(self):
        # Paiement initie via Paystack, puis bascule sur JEKO : le webhook
        # Paystack doit toujours regler le paiement en cours.
        headers, booking, payment = self.initiate_pending_payment()
        self.use_jeko_provider()

        response = self.post_payment_webhook(self.paystack_transaction_data(payment))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.payment_status_from_api(headers, booking["id"])["status"], "success"
        )
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "confirmed")

    def test_reinitiate_jeko_payment_generates_new_reference(self):
        headers, booking, first_payment = self.initiate_jeko_pending_payment()

        response, _ = self.initiate_jeko_payment(
            headers,
            {"booking_id": booking["id"], "payment_method": "orange"},
        )

        self.assertEqual(response.status_code, 200)
        second_payment = response.get_json()["payment"]
        self.assertEqual(second_payment["id"], first_payment["id"])
        self.assertNotEqual(
            second_payment["provider_reference"], first_payment["provider_reference"]
        )
        self.assertEqual(self.payments_count(booking["id"]), 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
