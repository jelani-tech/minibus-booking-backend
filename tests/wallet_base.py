"""Socle commun aux tests wallet : base propre, second client, helpers d'accès.

Les tests tournent sur une vraie base Postgres (cf. tests/base.py) : chaque
setUp remet les tables wallet à zéro pour les deux clients de test, dans l'ordre
imposé par les clés étrangères.
"""

import json
from uuid import uuid4

from tests.base import BackendApiTestCase


TEST_CUSTOMER_ID = "88888888-8888-8888-8888-888888888888"
TEST_AUTH_USER_ID = "99999999-9999-9999-9999-999999999999"
TEST_PHONE = "+2250100000003"

# Second client, cree par les tests : sert aux verifications d'autorisation
# (un client ne doit jamais voir ni le wallet ni les rechargements d'un autre).
OTHER_CUSTOMER_ID = "77777777-7777-7777-7777-777777777777"
OTHER_AUTH_USER_ID = "66666666-6666-6666-6666-666666666666"
OTHER_PHONE = "+2250100000009"

TEST_PASSWORD = "dev-password"
TEST_PASSWORD_HASH = "$2b$12$.MFBQ8RIgpwJyWHscoQ5vuFJ7Dgcaf36QbfbXeRbuInB9yhoGQtrW"

JEKO_WEBHOOK_TEST_SECRET = "jeko_test_webhook_secret"
PAYSTACK_WEBHOOK_TEST_SECRET = "sk_test_webhook_secret"
JEKO_TEST_PUBLIC_BASE_URL = "https://api.test.local"


class WalletTestCase(BackendApiTestCase):
    def setUp(self):
        from models.public import db

        self.app.config.update(
            WALLET_ENABLED=True,
            WALLET_TOPUP_ENABLED=True,
            WALLET_PAYMENT_ENABLED=True,
            WALLET_REFUND_TO_WALLET=True,
            WALLET_MIN_TOPUP_XOF=500,
            WALLET_MAX_TOPUP_XOF=200_000,
            WALLET_MAX_BALANCE_XOF=500_000,
            WALLET_DAILY_TOPUP_LIMIT_XOF=300_000,
            WALLET_TOPUP_RATE_LIMIT=10,
            WALLET_TOPUP_RATE_WINDOW_MINUTES=10,
            WALLET_TOPUP_REUSE_MINUTES=15,
            PAYMENT_PROVIDER="jeko",
            PAYMENT_PUBLIC_BASE_URL=JEKO_TEST_PUBLIC_BASE_URL,
            JEKO_WEBHOOK_SECRET=JEKO_WEBHOOK_TEST_SECRET,
            PAYSTACK_SECRET_KEY=PAYSTACK_WEBHOOK_TEST_SECRET,
            BOOKING_DEEPLINK_CALLBACK="",
        )

        with self.app.app_context():
            # Ordre impose par les cles etrangeres : ecritures, puis
            # rechargements, puis wallets.
            scope = "customer_id in (cast(:cid as uuid), cast(:other_cid as uuid))"
            for statement in (
                f"delete from public.wallet_entries where wallet_id in "
                f"  (select id from public.wallets where {scope})",
                f"delete from public.wallet_topups where {scope}",
                f"delete from public.wallets where {scope}",
                f"delete from public.payments where {scope}",
                f"delete from public.bookings where {scope}",
            ):
                db.session.execute(
                    db.text(statement),
                    {"cid": TEST_CUSTOMER_ID, "other_cid": OTHER_CUSTOMER_ID},
                )

            db.session.execute(
                db.text(
                    """
                    update public.trips
                    set capacity_booked = 0,
                        capacity_available = capacity_total - capacity_blocked,
                        planned_start_datetime = timezone('utc', now()) + interval '1 day'
                    """
                )
            )

            for auth_id, customer_id, phone, first_name in (
                (TEST_AUTH_USER_ID, TEST_CUSTOMER_ID, TEST_PHONE, "Jean"),
                (OTHER_AUTH_USER_ID, OTHER_CUSTOMER_ID, OTHER_PHONE, "Awa"),
            ):
                db.session.execute(
                    db.text(
                        """
                        insert into auth.users (id, phone, encrypted_password)
                        values (cast(:auth_id as uuid), :phone, :hash)
                        on conflict (phone) do update
                        set encrypted_password = excluded.encrypted_password
                        """
                    ),
                    {"auth_id": auth_id, "phone": phone, "hash": TEST_PASSWORD_HASH},
                )
                db.session.execute(
                    db.text(
                        """
                        insert into public.customers
                            (id, auth_user_id, first_name, last_name, phone, whatsapp_phone)
                        values (cast(:customer_id as uuid), cast(:auth_id as uuid),
                                :first_name, 'Client', :phone, :phone)
                        on conflict (id) do update
                        set auth_user_id = excluded.auth_user_id
                        """
                    ),
                    {
                        "customer_id": customer_id,
                        "auth_id": auth_id,
                        "phone": phone,
                        "first_name": first_name,
                    },
                )
            db.session.commit()

    # ── authentification ───────────────────────────────────────────────────

    def auth_headers(self, phone=TEST_PHONE):
        response = self.client.post(
            "/api/auth/login", json={"phone": phone, "password": TEST_PASSWORD}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return {"Authorization": f"Bearer {response.get_json()['access_token']}"}

    # ── accès direct à la base ─────────────────────────────────────────────

    def wallet_row(self, customer_id=TEST_CUSTOMER_ID):
        from models.public import db

        with self.app.app_context():
            row = db.session.execute(
                db.text(
                    "select * from public.wallets where customer_id = cast(:cid as uuid)"
                ),
                {"cid": customer_id},
            ).mappings().first()
            return dict(row) if row else None

    def wallet_balance(self, customer_id=TEST_CUSTOMER_ID):
        wallet = self.wallet_row(customer_id)
        return int(wallet["balance"]) if wallet else None

    def wallet_entries(self, customer_id=TEST_CUSTOMER_ID):
        from models.public import db

        with self.app.app_context():
            rows = db.session.execute(
                db.text(
                    """
                    select e.*
                    from public.wallet_entries e
                    join public.wallets w on w.id = e.wallet_id
                    where w.customer_id = cast(:cid as uuid)
                    order by e.created_at, e.id
                    """
                ),
                {"cid": customer_id},
            ).mappings().all()
            return [dict(row) for row in rows]

    def topup_row(self, topup_id):
        from models.public import db

        with self.app.app_context():
            row = db.session.execute(
                db.text("select * from public.wallet_topups where id = cast(:id as uuid)"),
                {"id": str(topup_id)},
            ).mappings().first()
            return dict(row) if row else None

    def set_wallet_status(self, status, customer_id=TEST_CUSTOMER_ID):
        from models.public import db

        with self.app.app_context():
            db.session.execute(
                db.text(
                    """
                    insert into public.wallets (customer_id, status)
                    values (cast(:cid as uuid), :status)
                    on conflict (customer_id) do update set status = excluded.status
                    """
                ),
                {"cid": customer_id, "status": status},
            )
            db.session.commit()

    def credit_wallet(self, amount, customer_id=TEST_CUSTOMER_ID, key=None):
        """Crédite directement le wallet via le repository (mise en place)."""
        from infrastructure.supabase_write_repositories import SupabaseWalletRepository
        from models.public import db

        with self.app.app_context():
            entry = SupabaseWalletRepository().post_entry(
                customer_id=customer_id,
                direction="credit",
                entry_type="promo_credit",
                amount=amount,
                idempotency_key=key or f"test:{uuid4().hex}",
                reference_type="manual",
                description="Crédit de test",
            )
            db.session.commit()
            return entry

    # ── réservations ───────────────────────────────────────────────────────

    def first_trip_id(self):
        response = self.client.get("/api/trips")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["trips"][0]["id"]

    def trip_stop_ids(self, trip_id):
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

    def create_booking(self, headers=None, seats=1):
        headers = headers or self.auth_headers()
        trip_id = self.first_trip_id()
        pickup_stop_id, dropoff_stop_id = self.trip_stop_ids(trip_id)
        response = self.client.post(
            "/api/bookings",
            headers=headers,
            json={
                "trip_id": trip_id,
                "number_of_seats": seats,
                "pickup_stop_id": pickup_stop_id,
                "dropoff_stop_id": dropoff_stop_id,
            },
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["booking"]

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

    def payment_row(self, booking_id):
        from models.public import db

        with self.app.app_context():
            row = db.session.execute(
                db.text(
                    """
                    select *
                    from public.payments
                    where booking_id = cast(:booking_id as uuid)
                    order by created_at desc
                    limit 1
                    """
                ),
                {"booking_id": booking_id},
            ).mappings().first()
            return dict(row) if row else None

    # ── webhooks signés ────────────────────────────────────────────────────

    def jeko_webhook_payload(self, reference, amount, status="success", currency="XOF"):
        return {
            "id": f"txn_{uuid4().hex[:8]}",
            "status": status,
            "amount": {"amount": amount, "currency": currency},
            "transactionType": "payment",
            "counterpartIdentifier": "+2250700000001",
            "paymentMethod": "wave",
            "transactionDetails": {"id": "pr_abc123", "reference": reference},
        }

    def post_jeko_webhook(self, payload):
        import hashlib
        import hmac

        body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(
            JEKO_WEBHOOK_TEST_SECRET.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return self.client.post(
            "/api/payments/jeko/webhook",
            data=body,
            headers={"Content-Type": "application/json", "Jeko-Signature": signature},
        )

    def post_paystack_webhook(self, data, event="charge.success"):
        import hashlib
        import hmac

        body = json.dumps({"event": event, "data": data}).encode("utf-8")
        signature = hmac.new(
            PAYSTACK_WEBHOOK_TEST_SECRET.encode("utf-8"), body, hashlib.sha512
        ).hexdigest()
        return self.client.post(
            "/api/payments/webhook",
            data=body,
            headers={"Content-Type": "application/json", "x-paystack-signature": signature},
        )
