"""Registre wallet : conservation, positivité, idempotence, concurrence (§ 11)."""

import random
import threading
from uuid import uuid4

from infrastructure.supabase_write_repositories import (
    InsufficientFundsError,
    SupabaseWalletRepository,
    WalletFrozenError,
)
from tests.wallet_base import TEST_CUSTOMER_ID, WalletTestCase


class WalletRepositoryTest(WalletTestCase):
    def repository(self):
        return SupabaseWalletRepository()

    def post(self, **kwargs):
        from models.public import db

        with self.app.app_context():
            entry = self.repository().post_entry(
                customer_id=kwargs.pop("customer_id", TEST_CUSTOMER_ID),
                idempotency_key=kwargs.pop("idempotency_key", f"test:{uuid4().hex}"),
                **kwargs,
            )
            db.session.commit()
            return entry

    def test_get_or_create_is_idempotent(self):
        from models.public import db

        with self.app.app_context():
            repository = self.repository()
            first = repository.get_or_create(TEST_CUSTOMER_ID)
            db.session.commit()
            second = repository.get_or_create(TEST_CUSTOMER_ID)
            db.session.commit()

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(int(first["balance"]), 0)
        self.assertEqual(first["status"], "active")
        self.assertEqual(first["currency"], "XOF")

    def test_credit_then_debit_tracks_balance_after(self):
        credit = self.post(direction="credit", entry_type="topup", amount=10000)
        debit = self.post(direction="debit", entry_type="booking_payment", amount=2500)

        self.assertEqual(int(credit["balance_after"]), 10000)
        self.assertEqual(int(debit["balance_after"]), 7500)
        self.assertEqual(self.wallet_balance(), 7500)

    def test_debit_above_balance_is_refused_without_writing(self):
        self.post(direction="credit", entry_type="topup", amount=1000)

        with self.assertRaises(InsufficientFundsError) as raised:
            self.post(direction="debit", entry_type="booking_payment", amount=2500)

        self.assertEqual(raised.exception.balance, 1000)
        self.assertEqual(raised.exception.required, 2500)
        self.assertEqual(raised.exception.missing, 1500)
        self.assertEqual(self.wallet_balance(), 1000)
        self.assertEqual(len(self.wallet_entries()), 1)

    def test_same_idempotency_key_applies_the_movement_once(self):
        key = f"topup:{uuid4()}"
        first = self.post(
            direction="credit", entry_type="topup", amount=5000, idempotency_key=key
        )
        second = self.post(
            direction="credit", entry_type="topup", amount=5000, idempotency_key=key
        )

        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(int(second["balance_after"]), 5000)
        self.assertEqual(self.wallet_balance(), 5000)
        self.assertEqual(len(self.wallet_entries()), 1)

    def test_frozen_wallet_refuses_debit_and_topup_but_accepts_refund(self):
        self.post(direction="credit", entry_type="topup", amount=10000)
        self.set_wallet_status("frozen")

        with self.assertRaises(WalletFrozenError):
            self.post(direction="debit", entry_type="booking_payment", amount=1000)
        with self.assertRaises(WalletFrozenError):
            self.post(direction="credit", entry_type="topup", amount=1000)

        refund = self.post(direction="credit", entry_type="booking_refund", amount=2500)

        self.assertEqual(int(refund["balance_after"]), 12500)
        self.assertEqual(self.wallet_balance(), 12500)

    def test_invalid_movements_are_rejected(self):
        for kwargs in (
            {"direction": "sideways", "entry_type": "topup", "amount": 100},
            {"direction": "credit", "entry_type": "not_a_type", "amount": 100},
            {"direction": "credit", "entry_type": "topup", "amount": 0},
            {"direction": "credit", "entry_type": "topup", "amount": -100},
        ):
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    self.post(**kwargs)
        self.assertEqual(self.wallet_entries(), [])

    def test_concurrent_debits_never_overdraw(self):
        """Deux débits simultanés du même wallet : le verrou de ligne sérialise,
        le second lit le solde déjà décrémenté et échoue proprement."""
        self.post(direction="credit", entry_type="topup", amount=3000)

        results = {}
        barrier = threading.Barrier(2)

        def debit(name):
            from models.public import db

            with self.app.app_context():
                try:
                    barrier.wait(timeout=10)
                    entry = SupabaseWalletRepository().post_entry(
                        customer_id=TEST_CUSTOMER_ID,
                        direction="debit",
                        entry_type="booking_payment",
                        amount=2000,
                        idempotency_key=f"concurrent:{name}:{uuid4().hex}",
                    )
                    db.session.commit()
                    results[name] = entry
                except Exception as e:  # noqa: BLE001 - on veut le type exact
                    db.session.rollback()
                    results[name] = e
                finally:
                    db.session.remove()

        threads = [threading.Thread(target=debit, args=(name,)) for name in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        outcomes = list(results.values())
        self.assertEqual(len(outcomes), 2)
        succeeded = [o for o in outcomes if isinstance(o, dict)]
        refused = [o for o in outcomes if isinstance(o, InsufficientFundsError)]
        self.assertEqual(len(succeeded), 1)
        self.assertEqual(len(refused), 1)
        self.assertEqual(self.wallet_balance(), 1000)

    def test_concurrent_get_or_create_yields_a_single_wallet(self):
        from models.public import db

        barrier = threading.Barrier(4)
        wallet_ids = []

        def create():
            with self.app.app_context():
                try:
                    barrier.wait(timeout=10)
                    wallet = SupabaseWalletRepository().get_or_create(TEST_CUSTOMER_ID)
                    db.session.commit()
                    wallet_ids.append(str(wallet["id"]))
                except Exception:
                    db.session.rollback()
                finally:
                    db.session.remove()

        threads = [threading.Thread(target=create) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)

        with self.app.app_context():
            count = db.session.execute(
                db.text(
                    "select count(*) from public.wallets where customer_id = cast(:cid as uuid)"
                ),
                {"cid": TEST_CUSTOMER_ID},
            ).scalar()
        self.assertEqual(count, 1)
        self.assertEqual(len(set(wallet_ids)), 1)

    def test_conservation_holds_after_a_random_sequence(self):
        random.seed(20260805)
        expected = 0
        for index in range(30):
            if expected > 500 and random.random() < 0.5:
                amount = random.randint(1, expected)
                self.post(
                    direction="debit",
                    entry_type="booking_payment",
                    amount=amount,
                    idempotency_key=f"seq:debit:{index}:{uuid4().hex}",
                )
                expected -= amount
            else:
                amount = random.randint(100, 5000)
                self.post(
                    direction="credit",
                    entry_type="topup",
                    amount=amount,
                    idempotency_key=f"seq:credit:{index}:{uuid4().hex}",
                )
                expected += amount

        entries = self.wallet_entries()
        computed = sum(
            int(e["amount"]) if e["direction"] == "credit" else -int(e["amount"])
            for e in entries
        )
        self.assertEqual(computed, expected)
        self.assertEqual(self.wallet_balance(), expected)
        # balance_after suit le cumul, ecriture par ecriture
        running = 0
        for entry in entries:
            running += (
                int(entry["amount"])
                if entry["direction"] == "credit"
                else -int(entry["amount"])
            )
            self.assertEqual(int(entry["balance_after"]), running)

        with self.app.app_context():
            self.assertEqual(self.repository().find_balance_divergences(), [])

    def test_audit_detects_a_tampered_balance(self):
        from models.public import db

        self.post(direction="credit", entry_type="topup", amount=4000)
        with self.app.app_context():
            db.session.execute(
                db.text(
                    """
                    update public.wallets
                    set balance = 9999
                    where customer_id = cast(:cid as uuid)
                    """
                ),
                {"cid": TEST_CUSTOMER_ID},
            )
            db.session.commit()
            divergences = self.repository().find_balance_divergences()

        self.assertEqual(len(divergences), 1)
        self.assertEqual(int(divergences[0]["balance"]), 9999)
        self.assertEqual(int(divergences[0]["computed_balance"]), 4000)
        self.assertEqual(int(divergences[0]["difference"]), 5999)

    def test_list_entries_paginates_descending(self):
        for index in range(5):
            self.post(
                direction="credit",
                entry_type="topup",
                amount=1000 + index,
                idempotency_key=f"page:{index}",
            )

        with self.app.app_context():
            first_page, has_more = self.repository().list_entries(
                customer_id=TEST_CUSTOMER_ID, limit=3
            )
            self.assertTrue(has_more)
            self.assertEqual(len(first_page), 3)

            cursor = first_page[-1]["created_at"].isoformat()
            second_page, still_more = self.repository().list_entries(
                customer_id=TEST_CUSTOMER_ID, limit=3, before=cursor
            )

        self.assertFalse(still_more)
        self.assertEqual(len(second_page), 2)
        self.assertEqual(int(first_page[0]["amount"]), 1004)
        self.assertEqual(int(second_page[-1]["amount"]), 1000)


if __name__ == "__main__":
    import unittest

    unittest.main()
