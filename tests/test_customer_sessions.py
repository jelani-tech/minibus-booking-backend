"""Sessions de l'app client : access token court, refresh token à usage unique."""

from flask_jwt_extended import create_access_token

from tests.base import BackendApiTestCase

CUSTOMER_PHONE = "+2250100000003"
CUSTOMER_PASSWORD = "dev-password"
CUSTOMER_ID = "88888888-8888-8888-8888-888888888888"


class CustomerSessionTest(BackendApiTestCase):
    def login(self):
        response = self.client.post(
            "/api/auth/login", json={"phone": CUSTOMER_PHONE, "password": CUSTOMER_PASSWORD}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    @staticmethod
    def bearer(access_token):
        return {"Authorization": f"Bearer {access_token}"}

    def test_login_returns_short_access_token_and_refresh_token(self):
        body = self.login()

        self.assertEqual(body["token_type"], "Bearer")
        self.assertEqual(body["expires_in"], 15 * 60)
        self.assertTrue(body["refresh_token"])
        me = self.client.get("/api/auth/me", headers=self.bearer(body["access_token"]))
        self.assertEqual(me.status_code, 200)

    def test_customer_sessions_are_independent(self):
        # Contrairement au chauffeur, un nouveau login client ne coupe pas les
        # autres appareils.
        first = self.login()
        self.login()

        me = self.client.get("/api/auth/me", headers=self.bearer(first["access_token"]))
        self.assertEqual(me.status_code, 200)

    def test_refresh_rotates_and_old_token_is_single_use(self):
        tokens = self.login()

        rotated = self.client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertEqual(rotated.status_code, 200)
        me = self.client.get(
            "/api/auth/me", headers=self.bearer(rotated.get_json()["access_token"])
        )
        self.assertEqual(me.status_code, 200)

        reuse = self.client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertEqual(reuse.status_code, 401)

    def test_refresh_requires_a_token(self):
        response = self.client.post("/api/auth/refresh", json={})
        self.assertEqual(response.status_code, 400)

    def test_unknown_refresh_token_is_refused(self):
        response = self.client.post("/api/auth/refresh", json={"refresh_token": "forged"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["code"], "invalid_refresh_token")

    def test_logout_revokes_access_and_refresh_tokens(self):
        tokens = self.login()
        headers = self.bearer(tokens["access_token"])

        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)

        me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.get_json()["code"], "session_revoked")
        refresh = self.client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertEqual(refresh.status_code, 401)

    def test_legacy_token_without_audience_is_refused(self):
        with self.app.app_context():
            legacy_token = create_access_token(identity=CUSTOMER_ID)

        me = self.client.get("/api/auth/me", headers=self.bearer(legacy_token))

        self.assertEqual(me.status_code, 401)
