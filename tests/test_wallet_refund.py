"""Paiement d'une réservation depuis le solde et recrédit à l'annulation (§ 11)."""

from unittest.mock import patch

from tests.wallet_base import OTHER_PHONE, WalletTestCase


class WalletBookingPaymentTest(WalletTestCase):
    def pay_from_wallet(self, booking_id, headers):
        return self.client.post(
            "/api/payments/initiate",
            headers=headers,
            json={"booking_id": booking_id, "payment_method": "wallet"},
        )

    def test_sufficient_balance_confirms_the_booking_synchronously(self):
        headers = self.auth_headers()
        self.credit_wallet(12500)
        booking = self.create_booking(headers=headers)
        price = int(round(float(booking["total_price"])))

        response = self.pay_from_wallet(booking["id"], headers)

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertIsNone(payload["payment_url"])
        self.assertEqual(payload["payment"]["status"], "success")
        self.assertEqual(payload["payment"]["provider"], "wallet")
        self.assertEqual(payload["wallet"]["balance"], 12500 - price)

        booking_row = self.booking_row(booking["id"])
        self.assertEqual(booking_row["booking_status"], "confirmed")
        self.assertEqual(booking_row["payment_status"], "paid")
        self.assertEqual(self.wallet_balance(), 12500 - price)

        payment = self.payment_row(booking["id"])
        self.assertEqual(payment["provider"], "wallet")
        self.assertEqual(payment["provider_reference"], f"WL-{booking['id']}")
        self.assertIsNone(payment["provider_payment_url"])
        self.assertIsNotNone(payment["paid_at"])

        entries = self.wallet_entries()
        debit = [e for e in entries if e["direction"] == "debit"]
        self.assertEqual(len(debit), 1)
        self.assertEqual(debit[0]["entry_type"], "booking_payment")
        self.assertEqual(int(debit[0]["amount"]), price)
        self.assertEqual(debit[0]["idempotency_key"], f"booking_payment:{booking['id']}")

    def test_insufficient_balance_returns_402_with_the_missing_amount(self):
        headers = self.auth_headers()
        booking = self.create_booking(headers=headers)
        price = int(round(float(booking["total_price"])))
        self.credit_wallet(price - 1000)

        response = self.pay_from_wallet(booking["id"], headers)

        self.assertEqual(response.status_code, 402)
        payload = response.get_json()
        self.assertEqual(payload["code"], "INSUFFICIENT_FUNDS")
        self.assertEqual(payload["balance"], price - 1000)
        self.assertEqual(payload["required"], price)
        self.assertEqual(payload["missing"], 1000)
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "pending")
        self.assertEqual(self.wallet_balance(), price - 1000)
        self.assertIsNone(self.payment_row(booking["id"]))

    def test_double_initiate_debits_only_once(self):
        headers = self.auth_headers()
        self.credit_wallet(50000)
        booking = self.create_booking(headers=headers)
        price = int(round(float(booking["total_price"])))

        first = self.pay_from_wallet(booking["id"], headers)
        second = self.pay_from_wallet(booking["id"], headers)

        self.assertEqual(first.status_code, 200)
        # La seconde tentative est arretee par le garde-fou « deja paye »
        self.assertEqual(second.status_code, 400)
        self.assertEqual(self.wallet_balance(), 50000 - price)
        self.assertEqual(
            len([e for e in self.wallet_entries() if e["direction"] == "debit"]), 1
        )

    def test_frozen_wallet_cannot_pay(self):
        headers = self.auth_headers()
        self.credit_wallet(50000)
        self.set_wallet_status("frozen")
        booking = self.create_booking(headers=headers)

        response = self.pay_from_wallet(booking["id"], headers)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "WALLET_FROZEN")
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "pending")

    def test_booking_of_another_customer_is_forbidden(self):
        headers = self.auth_headers()
        booking = self.create_booking(headers=headers)
        self.credit_wallet(50000, customer_id="77777777-7777-7777-7777-777777777777")

        response = self.pay_from_wallet(booking["id"], self.auth_headers(OTHER_PHONE))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "pending")

    def test_wallet_payment_is_refused_when_the_feature_is_off(self):
        self.app.config["WALLET_PAYMENT_ENABLED"] = False
        headers = self.auth_headers()
        self.credit_wallet(50000)
        booking = self.create_booking(headers=headers)

        response = self.pay_from_wallet(booking["id"], headers)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "WALLET_DISABLED")
        self.assertEqual(self.wallet_balance(), 50000)

    def test_payment_status_endpoint_reports_the_wallet_payment(self):
        headers = self.auth_headers()
        self.credit_wallet(50000)
        booking = self.create_booking(headers=headers)
        self.pay_from_wallet(booking["id"], headers)

        response = self.client.get(
            f"/api/payments/status/{booking['id']}", headers=headers
        )

        self.assertEqual(response.status_code, 200)
        payment = response.get_json()["payment"]
        self.assertEqual(payment["status"], "success")
        self.assertEqual(payment["provider"], "wallet")


class WalletRefundTest(WalletTestCase):
    def cancel(self, booking_id, headers):
        """Annulation avec JekoService mocké : le chemin wallet ne doit jamais
        l'appeler."""
        with patch("services.refund_service.JekoService") as mock_service:
            response = self.client.delete(f"/api/bookings/{booking_id}", headers=headers)
        return response, mock_service.return_value

    def paid_by_wallet(self):
        headers = self.auth_headers()
        self.credit_wallet(50000)
        booking = self.create_booking(headers=headers)
        response = self.client.post(
            "/api/payments/initiate",
            headers=headers,
            json={"booking_id": booking["id"], "payment_method": "wallet"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return headers, booking, int(round(float(booking["total_price"])))

    def paid_by_jeko(self):
        headers = self.auth_headers()
        booking = self.create_booking(headers=headers)
        with patch("routes.payment.JekoService") as mock_service:
            mock_service.return_value.initialize_payment.return_value = {
                "payment_url": "https://pay.jeko.local/redirect",
                "provider_payment_id": "pr_abc123",
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
        price = int(round(float(payment["amount"])))
        webhook = self.post_jeko_webhook(
            self.jeko_webhook_payload(payment["provider_reference"], price * 100)
        )
        self.assertEqual(webhook.status_code, 200)
        return headers, booking, price

    def paid_by_paystack(self):
        self.app.config["PAYMENT_PROVIDER"] = "paystack"
        headers = self.auth_headers()
        booking = self.create_booking(headers=headers)
        with patch("routes.payment.PaystackService") as mock_service:
            mock_service.return_value.initialize_payment.return_value = {
                "authorization_url": "https://paystack.local/redirect",
                "reference": "ps-ref-001",
                "status": "pending",
            }
            initiate = self.client.post(
                "/api/payments/initiate",
                headers=headers,
                json={"booking_id": booking["id"], "payment_email": "c@example.com"},
            )
        self.assertEqual(initiate.status_code, 200)
        payment = initiate.get_json()["payment"]
        price = int(round(float(payment["amount"])))
        webhook = self.post_paystack_webhook({
            "reference": payment["provider_reference"],
            "status": "success",
            "amount": price * 100,
            "currency": "XOF",
        })
        self.assertEqual(webhook.status_code, 200)
        return headers, booking, price

    def assert_refunded_to_wallet(self, response, booking_id, amount, expected_balance):
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        refund = response.get_json()["refund"]
        self.assertEqual(refund["status"], "completed")
        self.assertEqual(refund["destination"], "wallet")
        self.assertEqual(refund["amount"], amount)
        self.assertEqual(refund["wallet_balance"], expected_balance)
        self.assertEqual(self.wallet_balance(), expected_balance)

        booking_row = self.booking_row(booking_id)
        self.assertEqual(booking_row["booking_status"], "cancelled")
        self.assertEqual(booking_row["payment_status"], "refunded")
        self.assertEqual(self.payment_row(booking_id)["status"], "refunded")

        credits = [
            e for e in self.wallet_entries() if e["entry_type"] == "booking_refund"
        ]
        self.assertEqual(len(credits), 1)
        self.assertEqual(int(credits[0]["amount"]), amount)

    def test_cancelling_a_wallet_paid_booking_credits_the_wallet_back(self):
        headers, booking, price = self.paid_by_wallet()
        self.assertEqual(self.wallet_balance(), 50000 - price)

        response, service = self.cancel(booking["id"], headers)

        self.assert_refunded_to_wallet(response, booking["id"], price, 50000)
        service.create_transfer.assert_not_called()

    def test_cancelling_a_jeko_paid_booking_credits_the_wallet_without_transfer(self):
        headers, booking, price = self.paid_by_jeko()

        response, service = self.cancel(booking["id"], headers)

        self.assert_refunded_to_wallet(response, booking["id"], price, price)
        service.create_beneficiary_contact.assert_not_called()
        service.create_transfer.assert_not_called()

    def test_cancelling_a_paystack_paid_booking_no_longer_requires_manual_work(self):
        headers, booking, price = self.paid_by_paystack()

        response, service = self.cancel(booking["id"], headers)

        self.assert_refunded_to_wallet(response, booking["id"], price, price)
        self.assertNotEqual(self.payment_row(booking["id"])["status"], "refund_required")
        service.create_transfer.assert_not_called()

    def test_cancelling_an_unpaid_booking_credits_nothing(self):
        headers = self.auth_headers()
        booking = self.create_booking(headers=headers)

        response, _ = self.cancel(booking["id"], headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["refund"], {"status": "none"})
        self.assertEqual(self.wallet_entries(), [])

    def test_double_cancellation_credits_only_once(self):
        headers, booking, price = self.paid_by_jeko()

        first, _ = self.cancel(booking["id"], headers)
        second, _ = self.cancel(booking["id"], headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)
        self.assertIn("already cancelled", second.get_json()["error"])
        self.assertEqual(self.wallet_balance(), price)
        self.assertEqual(
            len([e for e in self.wallet_entries() if e["entry_type"] == "booking_refund"]),
            1,
        )

    def test_wallet_credit_failure_keeps_the_cancellation_and_flags_manual(self):
        headers, booking, price = self.paid_by_jeko()

        with patch(
            "services.refund_service.wallet_repository.post_entry",
            side_effect=Exception("wallet down"),
        ):
            response = self.client.delete(
                f"/api/bookings/{booking['id']}", headers=headers
            )

        self.assertEqual(response.status_code, 200)
        refund = response.get_json()["refund"]
        self.assertEqual(refund["status"], "manual")
        self.assertEqual(refund["reason"], "wallet_credit_failed")
        # L'annulation reste acquise, jamais annulee par un echec de remboursement
        self.assertEqual(self.booking_row(booking["id"])["booking_status"], "cancelled")
        payment = self.payment_row(booking["id"])
        self.assertEqual(payment["status"], "refund_required")
        self.assertEqual(
            payment["raw_provider_response"]["refund"]["reason"], "wallet_credit_failed"
        )

    def test_refund_falls_back_to_jeko_transfer_when_the_switch_is_off(self):
        """Tant que WALLET_REFUND_TO_WALLET est à false, le virement sortant
        reste le chemin nominal (§ 12, étape 5)."""
        headers, booking, price = self.paid_by_jeko()
        self.app.config["WALLET_REFUND_TO_WALLET"] = False

        with patch("services.refund_service.JekoService") as mock_service:
            service = mock_service.return_value
            service.create_beneficiary_contact.return_value = "contact-1"
            service.create_transfer.return_value = {
                "status": "pending",
                "transfer_id": "transfer-1",
                "reference": "unused",
                "raw": {"id": "transfer-1"},
            }
            response = self.client.delete(
                f"/api/bookings/{booking['id']}", headers=headers
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["refund"]["status"], "initiated")
        service.create_transfer.assert_called_once()
        self.assertEqual(self.wallet_entries(), [])

    def test_refund_credits_a_frozen_wallet(self):
        """Un wallet gelé refuse débits et rechargements, mais jamais un
        remboursement : le bloquer laisserait l'argent du client dans les limbes."""
        headers, booking, price = self.paid_by_jeko()
        self.set_wallet_status("frozen")

        response, _ = self.cancel(booking["id"], headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["refund"]["status"], "completed")
        self.assertEqual(self.wallet_balance(), price)


if __name__ == "__main__":
    import unittest

    unittest.main()
