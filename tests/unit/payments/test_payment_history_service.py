from datetime import date, datetime
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock

from schemas.payment_history import PaymentHistoryCreateRequest
from services.payment_history import payment_history_service
from tests.unit.helpers import AsyncContextManager


class PaymentHistoryCalculationTests(TestCase):
    def test_calculate_next_payment_date_advances_one_cycle_when_paid_early(self):
        result = payment_history_service.calculate_next_payment_date(date(2026, 3, 10), date(2026, 3, 1), "MONTHLY")

        self.assertEqual(result, date(2026, 4, 10))

    def test_calculate_next_payment_date_catches_up_when_payment_is_late(self):
        result = payment_history_service.calculate_next_payment_date(date(2026, 1, 10), date(2026, 3, 15), "MONTHLY")

        self.assertEqual(result, date(2026, 4, 10))


class PaymentHistoryServiceTests(IsolatedAsyncioTestCase):
    async def test_create_payment_rejects_inactive_subscription(self):
        conn = MagicMock()
        conn.transaction.return_value = AsyncContextManager()
        conn.fetchrow = AsyncMock(return_value={
            "id": 2,
            "user_id": 4,
            "price": Decimal("49.90"),
            "billing_cycle": "MONTHLY",
            "status": "CANCELED",
            "next_payment_date": date(2026, 2, 5),
        })

        result = await payment_history_service.create_payment(conn, 2, 4, PaymentHistoryCreateRequest())

        self.assertEqual(result, {"status": False, "message": "Cannot register payment for inactive subscription", "data": {}})

    async def test_create_payment_defaults_amount_and_updates_next_payment_date(self):
        conn = MagicMock()
        conn.transaction.return_value = AsyncContextManager()
        subscription = {
            "id": 2,
            "user_id": 4,
            "price": Decimal("49.90"),
            "billing_cycle": "MONTHLY",
            "status": "ACTIVE",
            "next_payment_date": date(2026, 2, 5),
        }
        payment = {
            "id": 11,
            "subscription_id": 2,
            "user_id": 4,
            "amount": Decimal("49.90"),
            "paid_at": date(2026, 2, 5),
            "payment_method": "credit_card",
            "reference": "ref-1",
            "notes": None,
            "created_at": datetime(2026, 2, 5, 10, 0, 0),
        }
        updated_subscription = {"id": 2, "next_payment_date": date(2026, 3, 5)}
        conn.fetchrow = AsyncMock(side_effect=[subscription, payment, updated_subscription])

        result = await payment_history_service.create_payment(
            conn,
            2,
            4,
            PaymentHistoryCreateRequest(paymentMethod="credit_card", reference="ref-1", paidAt=date(2026, 2, 5)),
        )

        insert_args = conn.fetchrow.await_args_list[1].args
        update_args = conn.fetchrow.await_args_list[2].args
        self.assertEqual(insert_args[1:], (2, 4, 49.9, date(2026, 2, 5), "credit_card", "ref-1", None))
        self.assertEqual(update_args[1:], (date(2026, 3, 5), 2, 4))
        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["payment"]["amount"], 49.9)
        self.assertEqual(result["data"]["subscription"]["nextPaymentDate"], "2026-03-05")

    async def test_get_user_payment_history_formats_rows_and_pagination(self):
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[{
            "id": 1,
            "subscription_id": 2,
            "user_id": 4,
            "amount": Decimal("49.90"),
            "paid_at": date(2026, 2, 5),
            "payment_method": "pix",
            "reference": "abc",
            "notes": "ok",
            "created_at": datetime(2026, 2, 5, 10, 0, 0),
        }])

        result = await payment_history_service.get_user_payment_history(conn, 4, None, None, None, 30, 0)

        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["payments"][0]["subscriptionId"], 2)
        self.assertEqual(result["data"]["pagination"], {"limit": 30, "offset": 0})
