"""Authentification des chauffeurs : login téléphone + PIN, appareil lié,
verrouillage, sessions, et cloisonnement des jetons par application."""

from models.public import db
from services.auth.pin import hash_pin
from tests.base import BackendApiTestCase

DRIVER_ID = "44444444-4444-4444-4444-444444444401"
DRIVER_AUTH_USER_ID = "44444444-4444-4444-4444-444444444402"
DRIVER_PHONE = "+2250100000111"
PARTNER_ID = "11111111-1111-1111-1111-111111111111"

PROVISIONAL_PIN = "482915"
NEW_PIN = "730641"
DEVICE_ID = "device-driver-test-1"
OTHER_DEVICE_ID = "device-driver-test-2"

CUSTOMER_PHONE = "+2250100000003"
CUSTOMER_PASSWORD = "dev-password"

GENERIC_ERROR = "Identifiants invalides. En cas de difficulté, contactez le support."


class DriverAuthTest(BackendApiTestCase):
    def setUp(self):
        self.app.config.update(DRIVER_PIN_MAX_ATTEMPTS=5)
        with self.app.app_context():
            for statement in (
                "delete from app_auth.login_attempts where phone = :phone",
                "delete from public.customers where phone = :phone",
                "delete from public.drivers where id = cast(:driver_id as uuid)",
                # Cascade sur app_auth.user_pins et app_auth.refresh_tokens.
                "delete from auth.users where phone = :phone",
            ):
                db.session.execute(
                    db.text(statement), {"phone": DRIVER_PHONE, "driver_id": DRIVER_ID}
                )

            db.session.execute(
                db.text(
                    "insert into auth.users (id, phone) values (cast(:id as uuid), :phone)"
                ),
                {"id": DRIVER_AUTH_USER_ID, "phone": DRIVER_PHONE},
            )
            db.session.execute(
                db.text(
                    """
                    insert into public.drivers
                        (id, auth_user_id, partner_id, first_name, last_name, phone, status)
                    values (cast(:id as uuid), cast(:auth_id as uuid), cast(:partner_id as uuid),
                            'Awa', 'Test', :phone, 'active')
                    """
                ),
                {
                    "id": DRIVER_ID,
                    "auth_id": DRIVER_AUTH_USER_ID,
                    "partner_id": PARTNER_ID,
                    "phone": DRIVER_PHONE,
                },
            )
            db.session.execute(
                db.text(
                    """
                    insert into app_auth.user_pins (user_id, pin_hash, must_change_pin)
                    values (cast(:user_id as uuid), :pin_hash, true)
                    """
                ),
                {"user_id": DRIVER_AUTH_USER_ID, "pin_hash": hash_pin(PROVISIONAL_PIN)},
            )
            db.session.commit()

    # ── helpers ────────────────────────────────────────────────────────────

    def login(self, pin=PROVISIONAL_PIN, device_id=DEVICE_ID, phone=DRIVER_PHONE):
        return self.client.post(
            "/api/driver/auth/login",
            json={"phone": phone, "pin": pin, "device_id": device_id},
        )

    def login_with_new_pin(self):
        """Premier login + changement de PIN : retourne les jetons utilisables."""
        tokens = self.login().get_json()
        response = self.client.put(
            "/api/driver/auth/pin",
            json={"current_pin": PROVISIONAL_PIN, "new_pin": NEW_PIN},
            headers=self.bearer(tokens["access_token"]),
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        tokens["access_token"] = response.get_json()["access_token"]
        return tokens

    @staticmethod
    def bearer(access_token):
        return {"Authorization": f"Bearer {access_token}"}

    def set_driver_status(self, status):
        with self.app.app_context():
            db.session.execute(
                db.text("update public.drivers set status = :status where id = cast(:id as uuid)"),
                {"status": status, "id": DRIVER_ID},
            )
            db.session.commit()

    def pin_row(self):
        with self.app.app_context():
            return db.session.execute(
                db.text("select * from app_auth.user_pins where user_id = cast(:id as uuid)"),
                {"id": DRIVER_AUTH_USER_ID},
            ).mappings().one()

    def last_attempt(self):
        with self.app.app_context():
            return db.session.execute(
                db.text(
                    """
                    select * from app_auth.login_attempts
                    where phone = :phone
                    order by created_at desc
                    limit 1
                    """
                ),
                {"phone": DRIVER_PHONE},
            ).mappings().one()

    def assert_generic_failure(self, response, reason):
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], GENERIC_ERROR)
        attempt = self.last_attempt()
        self.assertFalse(attempt["success"])
        self.assertEqual(attempt["failure_reason"], reason)

    # ── login ──────────────────────────────────────────────────────────────

    def test_first_login_registers_device_and_requires_pin_change(self):
        response = self.login()

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["must_change_pin"])
        self.assertEqual(body["driver"]["id"], DRIVER_ID)
        self.assertIn("refresh_token", body)
        self.assertEqual(body["expires_in"], 15 * 60)

        self.assertEqual(self.pin_row()["device_id"], DEVICE_ID)
        attempt = self.last_attempt()
        self.assertTrue(attempt["success"])
        self.assertEqual(attempt["device_id"], DEVICE_ID)

        # Tant que le PIN provisoire n'est pas changé, seule /auth/pin est ouverte.
        me = self.client.get("/api/driver/me", headers=self.bearer(body["access_token"]))
        self.assertEqual(me.status_code, 403)
        self.assertEqual(me.get_json()["code"], "pin_change_required")

    def test_pin_change_unlocks_driver_routes(self):
        tokens = self.login_with_new_pin()

        me = self.client.get("/api/driver/me", headers=self.bearer(tokens["access_token"]))
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["driver"]["phone"], DRIVER_PHONE)
        self.assertFalse(self.pin_row()["must_change_pin"])

        # L'ancien PIN ne fonctionne plus, le nouveau oui.
        self.assert_generic_failure(self.login(pin=PROVISIONAL_PIN), "invalid_pin")
        relogin = self.login(pin=NEW_PIN)
        self.assertEqual(relogin.status_code, 200)
        self.assertFalse(relogin.get_json()["must_change_pin"])

    def test_pin_change_rejects_invalid_new_pin(self):
        access_token = self.login().get_json()["access_token"]

        for new_pin, code in (
            ("12345", "invalid_pin_format"),
            ("12a456", "invalid_pin_format"),
            ("111111", "weak_pin"),
            ("123456", "weak_pin"),
            (PROVISIONAL_PIN, "pin_unchanged"),
        ):
            response = self.client.put(
                "/api/driver/auth/pin",
                json={"current_pin": PROVISIONAL_PIN, "new_pin": new_pin},
                headers=self.bearer(access_token),
            )
            self.assertEqual(response.status_code, 400, new_pin)
            self.assertEqual(response.get_json()["code"], code, new_pin)

    def test_pin_change_with_wrong_current_pin_counts_as_failure(self):
        access_token = self.login().get_json()["access_token"]

        response = self.client.put(
            "/api/driver/auth/pin",
            json={"current_pin": "000001", "new_pin": NEW_PIN},
            headers=self.bearer(access_token),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "invalid_current_pin")
        self.assertEqual(self.pin_row()["failed_attempts"], 1)

    def test_unknown_phone_gets_generic_error(self):
        response = self.login(phone="+2250100000999")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], GENERIC_ERROR)

    def test_login_from_another_device_is_refused(self):
        self.login()

        response = self.login(device_id=OTHER_DEVICE_ID)

        self.assert_generic_failure(response, "unknown_device")
        self.assertEqual(self.pin_row()["device_id"], DEVICE_ID)

    def test_inactive_driver_is_refused(self):
        self.set_driver_status("suspended")

        self.assert_generic_failure(self.login(), "driver_inactive")

    def test_account_locks_after_five_wrong_pins(self):
        for _ in range(4):
            self.assert_generic_failure(self.login(pin="000001"), "invalid_pin")

        self.assert_generic_failure(self.login(pin="000001"), "invalid_pin_locked")
        self.assertIsNotNone(self.pin_row()["locked_at"])

        # Même le bon PIN est refusé une fois le compte verrouillé.
        self.assert_generic_failure(self.login(), "locked")

    def test_successful_login_resets_failure_counter(self):
        self.login(pin="000001")
        self.assertEqual(self.pin_row()["failed_attempts"], 1)

        self.login()

        self.assertEqual(self.pin_row()["failed_attempts"], 0)

    def test_lock_revokes_open_sessions(self):
        access_token = self.login_with_new_pin()["access_token"]

        for _ in range(5):
            self.login(pin="000001")

        me = self.client.get("/api/driver/me", headers=self.bearer(access_token))
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.get_json()["code"], "session_revoked")

    def test_missing_fields_are_rejected(self):
        response = self.client.post(
            "/api/driver/auth/login", json={"phone": DRIVER_PHONE, "pin": PROVISIONAL_PIN}
        )
        self.assertEqual(response.status_code, 400)

    # ── sessions ───────────────────────────────────────────────────────────

    def test_new_login_revokes_previous_session(self):
        first = self.login_with_new_pin()

        second = self.login(pin=NEW_PIN)
        self.assertEqual(second.status_code, 200)

        me = self.client.get("/api/driver/me", headers=self.bearer(first["access_token"]))
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.get_json()["code"], "session_revoked")

        refresh = self.client.post(
            "/api/driver/auth/refresh", json={"refresh_token": first["refresh_token"]}
        )
        self.assertEqual(refresh.status_code, 401)

    def test_refresh_rotates_tokens(self):
        tokens = self.login_with_new_pin()

        response = self.client.post(
            "/api/driver/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        self.assertEqual(response.status_code, 200)
        rotated = response.get_json()
        self.assertNotEqual(rotated["refresh_token"], tokens["refresh_token"])
        me = self.client.get("/api/driver/me", headers=self.bearer(rotated["access_token"]))
        self.assertEqual(me.status_code, 200)

    def test_refresh_token_reuse_revokes_the_session(self):
        tokens = self.login_with_new_pin()
        rotated = self.client.post(
            "/api/driver/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).get_json()

        reuse = self.client.post(
            "/api/driver/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        self.assertEqual(reuse.status_code, 401)
        self.assertEqual(reuse.get_json()["code"], "invalid_refresh_token")
        # Le jeton légitime issu de la rotation est lui aussi coupé.
        me = self.client.get("/api/driver/me", headers=self.bearer(rotated["access_token"]))
        self.assertEqual(me.status_code, 401)

    def test_refresh_is_refused_for_suspended_driver(self):
        tokens = self.login_with_new_pin()
        self.set_driver_status("suspended")

        response = self.client.post(
            "/api/driver/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        self.assertEqual(response.status_code, 401)

    def test_logout_revokes_the_session(self):
        tokens = self.login_with_new_pin()
        headers = self.bearer(tokens["access_token"])

        self.assertEqual(self.client.post("/api/driver/auth/logout", headers=headers).status_code, 200)

        self.assertEqual(self.client.get("/api/driver/me", headers=headers).status_code, 401)
        refresh = self.client.post(
            "/api/driver/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        self.assertEqual(refresh.status_code, 401)

    # ── cloisonnement des applications ─────────────────────────────────────

    def customer_tokens(self):
        response = self.client.post(
            "/api/auth/login", json={"phone": CUSTOMER_PHONE, "password": CUSTOMER_PASSWORD}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def test_customer_token_is_refused_on_driver_routes(self):
        access_token = self.customer_tokens()["access_token"]

        me = self.client.get("/api/driver/me", headers=self.bearer(access_token))

        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.get_json()["code"], "invalid_audience")

    def test_driver_token_is_refused_on_customer_routes(self):
        access_token = self.login_with_new_pin()["access_token"]

        me = self.client.get("/api/auth/me", headers=self.bearer(access_token))

        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.get_json()["code"], "invalid_audience")

    def test_customer_refresh_token_is_refused_on_driver_refresh(self):
        refresh_token = self.customer_tokens()["refresh_token"]

        response = self.client.post(
            "/api/driver/auth/refresh", json={"refresh_token": refresh_token}
        )

        self.assertEqual(response.status_code, 401)

    def test_driver_can_register_as_customer_with_same_phone(self):
        response = self.client.post(
            "/api/auth/register",
            json={"phone": DRIVER_PHONE, "password": "client-password", "name": "Awa Test"},
        )

        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        with self.app.app_context():
            customer = db.session.execute(
                db.text("select auth_user_id from public.customers where phone = :phone"),
                {"phone": DRIVER_PHONE},
            ).mappings().one()
        self.assertEqual(str(customer["auth_user_id"]), DRIVER_AUTH_USER_ID)

        # Le PIN chauffeur et le mot de passe client restent distincts.
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/auth/login", json={"phone": DRIVER_PHONE, "password": PROVISIONAL_PIN}
            ).status_code,
            401,
        )
