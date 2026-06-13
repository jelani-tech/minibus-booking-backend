from unittest.mock import patch

from tests.base import BackendApiTestCase
from models.public import db

class AuthResetPasswordTest(BackendApiTestCase):
    test_phones = (
        "+2250100000099",
        "+2250100000088",
        "+2250100000077",
    )

    def setUp(self):
        # Nettoyage des anciennes données de test si elles existent
        with self.app.app_context():
            for phone in self.test_phones:
                db.session.execute(
                    db.text("delete from auth.password_resets where phone = :phone"),
                    {"phone": phone}
                )
                # Supprimer le client et l'utilisateur s'ils existent
                customer = db.session.execute(
                    db.text("select id from public.customers where phone = :phone"),
                    {"phone": phone}
                ).mappings().first()
                if customer:
                    db.session.execute(
                        db.text("delete from public.bookings where customer_id = :id"),
                        {"id": customer["id"]}
                    )
                    db.session.execute(
                        db.text("delete from public.payments where customer_id = :id"),
                        {"id": customer["id"]}
                    )
                    db.session.execute(
                        db.text("delete from public.customers where id = :id"),
                        {"id": customer["id"]}
                    )
                db.session.execute(
                    db.text("delete from auth.users where phone = :phone"),
                    {"phone": phone}
                )
            db.session.commit()

    @patch("routes.auth.email_service.send_reset_otp_email", return_value=True)
    def test_complete_reset_password_flow(self, _mock_send_email):
        # 1. Inscrire un nouvel utilisateur de test
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "phone": "+2250100000099",
                "password": "old-password",
                "name": "Jean Reset Test",
                "email": "jean.reset.test@example.com"
            }
        )
        self.assertEqual(register_response.status_code, 201)

        # 2. Demander une réinitialisation de mot de passe
        request_response = self.client.post(
            "/api/auth/reset-password/request",
            json={"phone": "+2250100000099"}
        )
        self.assertEqual(request_response.status_code, 200)
        req_data = request_response.get_json()
        self.assertIn("email", req_data)
        self.assertTrue(req_data["email"].startswith("je"))
        self.assertTrue(req_data["email"].endswith("@example.com"))

        # 3. Récupérer l'OTP depuis la base de données
        with self.app.app_context():
            otp_record = db.session.execute(
                db.text("select * from auth.password_resets where phone = :phone and used = false"),
                {"phone": "+2250100000099"}
            ).mappings().first()
            self.assertIsNotNone(otp_record)
            otp_code = otp_record["otp_code"]

        # 4. Effectuer la réinitialisation de mot de passe avec le bon OTP
        reset_response = self.client.post(
            "/api/auth/reset-password/reset",
            json={
                "phone": "+2250100000099",
                "otp_code": otp_code,
                "new_password": "new-password-123"
            }
        )
        self.assertEqual(reset_response.status_code, 200)
        self.assertEqual(reset_response.get_json()["message"], "Votre mot de passe a été réinitialisé avec succès")

        # 5. Tenter de se connecter avec l'ancien mot de passe (doit échouer)
        login_fail_response = self.client.post(
            "/api/auth/login",
            json={
                "phone": "+2250100000099",
                "password": "old-password"
            }
        )
        self.assertEqual(login_fail_response.status_code, 401)

        # 6. Se connecter avec le nouveau mot de passe (doit réussir)
        login_success_response = self.client.post(
            "/api/auth/login",
            json={
                "phone": "+2250100000099",
                "password": "new-password-123"
            }
        )
        self.assertEqual(login_success_response.status_code, 200)
        self.assertIn("access_token", login_success_response.get_json())

    def test_request_reset_requires_customer_email(self):
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "phone": "+2250100000088",
                "password": "old-password",
                "name": "No Email Reset Test"
            }
        )
        self.assertEqual(register_response.status_code, 201)

        request_response = self.client.post(
            "/api/auth/reset-password/request",
            json={"phone": "+2250100000088"}
        )

        self.assertEqual(request_response.status_code, 400)
        self.assertIn("Aucune adresse e-mail", request_response.get_json()["error"])

    @patch("routes.auth.email_service.send_reset_otp_email", return_value=False)
    def test_failed_email_send_rolls_back_password_reset(self, _mock_send_email):
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "phone": "+2250100000077",
                "password": "old-password",
                "name": "Email Failure Reset Test",
                "email": "email.failure.reset@example.com"
            }
        )
        self.assertEqual(register_response.status_code, 201)

        request_response = self.client.post(
            "/api/auth/reset-password/request",
            json={"phone": "+2250100000077"}
        )

        self.assertEqual(request_response.status_code, 500)
        with self.app.app_context():
            otp_count = db.session.execute(
                db.text("select count(*) from auth.password_resets where phone = :phone"),
                {"phone": "+2250100000077"}
            ).scalar_one()
        self.assertEqual(otp_count, 0)
