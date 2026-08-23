"""Routes wallet : lecture, rechargement, règlement webhook/callback (§ 11)."""

from unittest.mock import patch
from uuid import uuid4

from tests.wallet_base import (
    JEKO_TEST_PUBLIC_BASE_URL,
    OTHER_PHONE,
    TEST_CUSTOMER_ID,
    WalletTestCase,
)


class WalletReadRoutesTest(WalletTestCase):
    def test_get_wallet_creates_it_lazily(self):
        self.assertIsNone(self.wallet_row())

        response = self.client.get("/api/wallet", headers=self.auth_headers())

        self.assertEqual(response.status_code, 200)
        wallet = response.get_json()["wallet"]
        self.assertEqual(wallet["balance"], 0)
        self.assertEqual(wallet["currency"], "XOF")
        self.assertEqual(wallet["status"], "active")
        self.assertIsNotNone(self.wallet_row())

    def test_wallet_routes_require_authentication(self):
        for path in ("/api/wallet", "/api/wallet/transactions", "/api/wallet/topups"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

    def test_wallet_routes_are_hidden_when_feature_is_disabled(self):
        self.app.config["WALLET_ENABLED"] = False

        response = self.client.get("/api/wallet", headers=self.auth_headers())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["code"], "WALLET_DISABLED")

    def test_transactions_are_scoped_to_the_caller(self):
        self.credit_wallet(5000)
        self.credit_wallet(3000, customer_id="77777777-7777-7777-7777-777777777777")

        response = self.client.get(
            "/api/wallet/transactions", headers=self.auth_headers()
        )

        self.assertEqual(response.status_code, 200)
        transactions = response.get_json()["transactions"]
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]["amount"], 5000)
        self.assertEqual(transactions[0]["balance_after"], 5000)
        self.assertEqual(transactions[0]["direction"], "credit")
        # Le releve ne fuit jamais les donnees brutes provider
        self.assertNotIn("metadata", transactions[0])

    def test_transactions_pagination_walks_the_whole_statement(self):
        for _ in range(5):
            self.credit_wallet(1000)
        headers = self.auth_headers()

        first = self.client.get(
            "/api/wallet/transactions?limit=3", headers=headers
        ).get_json()
        self.assertTrue(first["has_more"])
        self.assertEqual(len(first["transactions"]), 3)

        second = self.client.get(
            "/api/wallet/transactions",
            query_string={"limit": 3, "before": first["next_before"]},
            headers=headers,
        ).get_json()

        self.assertFalse(second["has_more"])
        self.assertEqual(len(second["transactions"]), 2)
        seen = {t["id"] for t in first["transactions"]} | {
            t["id"] for t in second["transactions"]
        }
        self.assertEqual(len(seen), 5)

    def test_transactions_reject_an_invalid_cursor(self):
        response = self.client.get(
            "/api/wallet/transactions?before=hier", headers=self.auth_headers()
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "INVALID_CURSOR")


class WalletTopupRoutesTest(WalletTestCase):
    JEKO_CHECKOUT_URL = "https://pay.jeko.local/redirect"

    def create_topup(self, payload=None, headers=None, checkout=None, extra_headers=None):
        headers = dict(headers or self.auth_headers())
        if extra_headers:
            headers.update(extra_headers)
        with patch("routes.wallet.JekoService") as mock_service:
            mock_service.return_value.initialize_payment.return_value = (
                checkout
                if checkout is not None
                else {
                    "payment_url": self.JEKO_CHECKOUT_URL,
                    "provider_payment_id": "pr_abc123",
                    "status": "pending",
                    "raw": {"id": "pr_abc123"},
                }
            )
            response = self.client.post(
                "/api/wallet/topups",
                headers=headers,
                json=payload if payload is not None else {
                    "amount": 10000,
                    "payment_method": "wave",
                },
            )
        return response, mock_service.return_value.initialize_payment

    def test_create_topup_returns_checkout_url(self):
        response, mock_initialize = self.create_topup()

        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        payload = response.get_json()
        topup = payload["topup"]
        self.assertEqual(payload["payment_url"], self.JEKO_CHECKOUT_URL)
        self.assertEqual(topup["amount"], 10000)
        self.assertEqual(topup["status"], "pending")
        self.assertEqual(topup["payment_method"], "wave")
        self.assertTrue(topup["reference"].startswith("TU-"))

        kwargs = mock_initialize.call_args.kwargs
        # Le x100 reste a la frontiere provider : la table est en francs.
        self.assertEqual(kwargs["amount_cents"], 10000 * 100)
        self.assertEqual(kwargs["reference"], topup["reference"])
        expected_callback = (
            f"{JEKO_TEST_PUBLIC_BASE_URL}/api/payments/callback?provider=jeko"
            f"&reference={topup['reference']}&topup_id={topup['id']}"
        )
        self.assertEqual(kwargs["success_url"], expected_callback)
        self.assertEqual(kwargs["error_url"], expected_callback)
        # Aucun credit tant que le provider n'a pas confirme
        self.assertEqual(self.wallet_balance(), 0)

    def test_topup_never_sends_the_deeplink_to_the_provider(self):
        self.app.config["BOOKING_DEEPLINK_CALLBACK"] = "jelani://payment-callback"

        response, mock_initialize = self.create_topup()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            mock_initialize.call_args.kwargs["success_url"].startswith("https://")
        )

    def test_invalid_amounts_are_rejected(self):
        for amount in (None, 0, -100, "beaucoup", 499, 200_001, 1000.5, True):
            with self.subTest(amount=amount):
                response, mock_initialize = self.create_topup(
                    {"amount": amount, "payment_method": "wave"}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["code"], "INVALID_AMOUNT")
                mock_initialize.assert_not_called()

    def test_invalid_payment_method_is_rejected_for_jeko(self):
        for payload in ({"amount": 10000}, {"amount": 10000, "payment_method": "paypal"}):
            with self.subTest(payload=payload):
                response, mock_initialize = self.create_topup(payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["code"], "INVALID_PAYMENT_METHOD")
                mock_initialize.assert_not_called()

    def test_balance_cap_blocks_the_top_up_before_charging(self):
        self.app.config["WALLET_MAX_BALANCE_XOF"] = 12000
        self.credit_wallet(10000)

        response, mock_initialize = self.create_topup()

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["code"], "TOPUP_LIMIT_REACHED")
        mock_initialize.assert_not_called()

    def test_daily_limit_blocks_the_top_up(self):
        self.app.config["WALLET_DAILY_TOPUP_LIMIT_XOF"] = 15000
        from models.public import db

        with self.app.app_context():
            from infrastructure.supabase_write_repositories import (
                SupabaseWalletRepository,
            )

            SupabaseWalletRepository().post_entry(
                customer_id=TEST_CUSTOMER_ID,
                direction="credit",
                entry_type="topup",
                amount=10000,
                idempotency_key=f"topup:{uuid4()}",
            )
            db.session.commit()

        response, mock_initialize = self.create_topup()

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["code"], "TOPUP_LIMIT_REACHED")
        mock_initialize.assert_not_called()

    def test_rate_limit_blocks_repeated_attempts(self):
        self.app.config["WALLET_TOPUP_RATE_LIMIT"] = 2
        headers = self.auth_headers()

        # Montants distincts : sinon la fenêtre de réutilisation rendrait le
        # même rechargement au lieu d'en créer un second.
        for amount in (10000, 11000):
            response, _ = self.create_topup(
                {"amount": amount, "payment_method": "wave"}, headers=headers
            )
            self.assertEqual(response.status_code, 201)

        blocked, mock_initialize = self.create_topup(
            {"amount": 7000, "payment_method": "wave"}, headers=headers
        )

        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.get_json()["code"], "TOPUP_LIMIT_REACHED")
        mock_initialize.assert_not_called()

    def test_frozen_wallet_refuses_top_up(self):
        self.set_wallet_status("frozen")

        response, mock_initialize = self.create_topup()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "WALLET_FROZEN")
        mock_initialize.assert_not_called()

    def test_identical_pending_top_up_is_reused(self):
        headers = self.auth_headers()
        first, _ = self.create_topup(headers=headers)
        second, mock_initialize = self.create_topup(headers=headers)

        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            second.get_json()["topup"]["id"], first.get_json()["topup"]["id"]
        )
        mock_initialize.assert_not_called()

    def test_idempotency_key_header_wins_over_the_reuse_window(self):
        headers = self.auth_headers()
        key = {"Idempotency-Key": "mobile-key-1"}

        first, _ = self.create_topup(headers=headers, extra_headers=key)
        # Montant different : la fenetre de reuse ne s'appliquerait pas, mais la
        # cle transmise par le mobile fait foi.
        second, mock_initialize = self.create_topup(
            {"amount": 20000, "payment_method": "wave"},
            headers=headers,
            extra_headers=key,
        )

        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            second.get_json()["topup"]["id"], first.get_json()["topup"]["id"]
        )
        self.assertEqual(second.get_json()["topup"]["amount"], 10000)
        mock_initialize.assert_not_called()

    def test_provider_failure_returns_503_and_keeps_the_attempt_pending(self):
        with patch("routes.wallet.JekoService") as mock_service:
            mock_service.return_value.initialize_payment.side_effect = Exception("boom")
            response = self.client.post(
                "/api/wallet/topups",
                headers=self.auth_headers(),
                json={"amount": 10000, "payment_method": "wave"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["code"], "PROVIDER_UNAVAILABLE")

        listed = self.client.get(
            "/api/wallet/topups", headers=self.auth_headers()
        ).get_json()["topups"]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["status"], "pending")
        self.assertEqual(self.wallet_balance(), 0)

    def test_provider_without_checkout_url_returns_503(self):
        response, _ = self.create_topup(
            checkout={"payment_url": None, "provider_payment_id": "pr_x"}
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["code"], "PROVIDER_UNAVAILABLE")

    def test_get_topup_of_another_customer_is_forbidden(self):
        response, _ = self.create_topup()
        topup_id = response.get_json()["topup"]["id"]

        other = self.client.get(
            f"/api/wallet/topups/{topup_id}", headers=self.auth_headers(OTHER_PHONE)
        )

        self.assertEqual(other.status_code, 403)
        self.assertEqual(other.get_json()["code"], "FORBIDDEN")

    def test_get_unknown_topup_returns_404(self):
        response = self.client.get(
            f"/api/wallet/topups/{uuid4()}", headers=self.auth_headers()
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["code"], "NOT_FOUND")


class WalletTopupSettlementTest(WalletTestCase):
    def open_topup(self, amount=10000):
        with patch("routes.wallet.JekoService") as mock_service:
            mock_service.return_value.initialize_payment.return_value = {
                "payment_url": "https://pay.jeko.local/redirect",
                "provider_payment_id": "pr_abc123",
                "status": "pending",
                "raw": {"id": "pr_abc123"},
            }
            response = self.client.post(
                "/api/wallet/topups",
                headers=self.auth_headers(),
                json={"amount": amount, "payment_method": "wave"},
            )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["topup"]

    def test_successful_webhook_credits_the_wallet_once(self):
        topup = self.open_topup()

        response = self.post_jeko_webhook(
            self.jeko_webhook_payload(topup["reference"], topup["amount"] * 100)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.wallet_balance(), 10000)
        row = self.topup_row(topup["id"])
        self.assertEqual(row["status"], "success")
        self.assertIsNotNone(row["credited_at"])
        entries = self.wallet_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["entry_type"], "topup")
        self.assertEqual(entries[0]["idempotency_key"], f"topup:{topup['id']}")

    def test_replayed_webhook_credits_only_once(self):
        topup = self.open_topup()
        payload = self.jeko_webhook_payload(topup["reference"], topup["amount"] * 100)

        for _ in range(3):
            self.assertEqual(self.post_jeko_webhook(payload).status_code, 200)

        self.assertEqual(self.wallet_balance(), 10000)
        self.assertEqual(len(self.wallet_entries()), 1)

    def test_webhook_and_callback_race_credits_once_in_either_order(self):
        for callback_first in (False, True):
            with self.subTest(callback_first=callback_first):
                self.setUp()
                topup = self.open_topup()
                payload = self.jeko_webhook_payload(
                    topup["reference"], topup["amount"] * 100
                )
                verification = {
                    "status": "success",
                    "amount": topup["amount"] * 100,
                    "currency": "XOF",
                    "reference": topup["reference"],
                    "provider_payment_id": "pr_abc123",
                    "raw": {},
                }

                def call_callback():
                    with patch("routes.payment.JekoService") as mock_service:
                        mock_service.return_value.verify_payment.return_value = verification
                        return self.client.get(
                            "/api/payments/callback",
                            query_string={
                                "provider": "jeko",
                                "reference": topup["reference"],
                                "topup_id": topup["id"],
                            },
                        )

                if callback_first:
                    self.assertEqual(call_callback().status_code, 200)
                    self.assertEqual(self.post_jeko_webhook(payload).status_code, 200)
                else:
                    self.assertEqual(self.post_jeko_webhook(payload).status_code, 200)
                    self.assertEqual(call_callback().status_code, 200)

                self.assertEqual(self.wallet_balance(), 10000)
                self.assertEqual(len(self.wallet_entries()), 1)

    def test_amount_mismatch_never_credits(self):
        topup = self.open_topup()

        response = self.post_jeko_webhook(
            self.jeko_webhook_payload(topup["reference"], 1)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.wallet_balance(), 0)
        self.assertEqual(self.wallet_entries(), [])
        self.assertEqual(self.topup_row(topup["id"])["status"], "pending")

    def test_currency_mismatch_never_credits(self):
        topup = self.open_topup()

        response = self.post_jeko_webhook(
            self.jeko_webhook_payload(
                topup["reference"], topup["amount"] * 100, currency="EUR"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.wallet_balance(), 0)

    def test_failed_webhook_marks_the_topup_without_touching_the_balance(self):
        topup = self.open_topup()

        response = self.post_jeko_webhook(
            self.jeko_webhook_payload(
                topup["reference"], topup["amount"] * 100, status="error"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.topup_row(topup["id"])["status"], "failed")
        self.assertEqual(self.wallet_balance(), 0)

    def test_success_after_failure_still_credits(self):
        topup = self.open_topup()
        self.post_jeko_webhook(
            self.jeko_webhook_payload(
                topup["reference"], topup["amount"] * 100, status="error"
            )
        )

        self.post_jeko_webhook(
            self.jeko_webhook_payload(topup["reference"], topup["amount"] * 100)
        )

        self.assertEqual(self.topup_row(topup["id"])["status"], "success")
        self.assertEqual(self.wallet_balance(), 10000)

    def test_failure_after_success_never_downgrades(self):
        topup = self.open_topup()
        self.post_jeko_webhook(
            self.jeko_webhook_payload(topup["reference"], topup["amount"] * 100)
        )

        self.post_jeko_webhook(
            self.jeko_webhook_payload(
                topup["reference"], topup["amount"] * 100, status="error"
            )
        )

        self.assertEqual(self.topup_row(topup["id"])["status"], "success")
        self.assertEqual(self.wallet_balance(), 10000)
        self.assertEqual(len(self.wallet_entries()), 1)

    def test_topup_status_endpoint_returns_the_new_balance(self):
        topup = self.open_topup()
        self.post_jeko_webhook(
            self.jeko_webhook_payload(topup["reference"], topup["amount"] * 100)
        )

        response = self.client.get(
            f"/api/wallet/topups/{topup['id']}", headers=self.auth_headers()
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["topup"]["status"], "success")
        self.assertIsNotNone(payload["topup"]["credited_at"])
        self.assertEqual(payload["wallet"]["balance"], 10000)
        self.assertEqual(payload["wallet"]["currency"], "XOF")

    def test_a_booking_reference_is_never_routed_to_the_wallet(self):
        """Sans préfixe TU-, l'événement va au règlement de paiement : le wallet
        n'est pas touché et la réservation est réglée normalement."""
        headers = self.auth_headers()
        booking = self.create_booking(headers=headers)
        with patch("routes.payment.JekoService") as mock_service:
            mock_service.return_value.initialize_payment.return_value = {
                "payment_url": "https://pay.jeko.local/redirect",
                "provider_payment_id": "pr_booking",
                "status": "pending",
                "raw": {},
            }
            initiate = self.client.post(
                "/api/payments/initiate",
                headers=headers,
                json={"booking_id": booking["id"], "payment_method": "wave"},
            )
        self.assertEqual(initiate.status_code, 200)
        payment = initiate.get_json()["payment"]

        response = self.post_jeko_webhook(
            self.jeko_webhook_payload(
                payment["provider_reference"],
                int(round(float(payment["amount"]) * 100)),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "confirmed")
        # Le wallet n'a meme pas ete touche : aucune ligne creee
        self.assertIsNone(self.wallet_row())
        self.assertEqual(self.wallet_entries(), [])

    def test_unknown_topup_reference_returns_200(self):
        response = self.post_jeko_webhook(
            self.jeko_webhook_payload("TU-INCONNUE", 10000)
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.wallet_entries(), [])

    def test_paystack_webhook_settles_a_topup_by_prefix(self):
        self.app.config["PAYMENT_PROVIDER"] = "paystack"
        with patch("routes.wallet.PaystackService") as mock_service:
            mock_service.return_value.initialize_payment.return_value = {
                "authorization_url": "https://paystack.local/redirect",
                "reference": "ignored-by-us",
                "status": "pending",
            }
            response = self.client.post(
                "/api/wallet/topups",
                headers=self.auth_headers(),
                json={"amount": 5000},
            )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        topup = response.get_json()["topup"]
        # La reference imposee par nous, pas celle rendue par Paystack
        self.assertTrue(topup["reference"].startswith("TU-"))

        webhook = self.post_paystack_webhook({
            "reference": topup["reference"],
            "status": "success",
            "amount": 5000 * 100,
            "currency": "XOF",
        })

        self.assertEqual(webhook.status_code, 200)
        self.assertEqual(self.wallet_balance(), 5000)


if __name__ == "__main__":
    import unittest

    unittest.main()
