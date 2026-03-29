from datetime import date, datetime
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock

from asyncpg.exceptions import UniqueViolationError

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
        self.assertEqual(insert_args[1:], (2, 4, date(2026, 2, 5), 49.9, date(2026, 2, 5), "credit_card", "ref-1", None))
        self.assertEqual(update_args[1:], (date(2026, 3, 5), 2, 4, "MONTHLY"))
        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["payment"]["amount"], 49.9)
        self.assertEqual(result["data"]["subscription"]["nextPaymentDate"], "2026-03-05")

    async def test_create_payment_returns_domain_error_when_reference_date_already_exists(self):
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
        conn.fetchrow = AsyncMock(side_effect=[subscription, UniqueViolationError("duplicate key value violates unique constraint")])

        result = await payment_history_service.create_payment(
            conn,
            2,
            4,
            PaymentHistoryCreateRequest(paymentMethod="credit_card", paidAt=date(2026, 2, 5)),
        )

        self.assertEqual(result, {"status": False, "message": "Payment already registered for this reference date", "data": {}})

    async def test_create_payment_returns_infrastructure_error_when_database_operation_fails(self):
        conn = MagicMock()
        conn.transaction.return_value = AsyncContextManager()
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("database unavailable"))

        result = await payment_history_service.create_payment(
            conn,
            2,
            4,
            PaymentHistoryCreateRequest(paymentMethod="credit_card", paidAt=date(2026, 2, 5)),
        )

        self.assertEqual(result, {"status": False, "message": "An error occurred while registering payment", "data": {}})

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

        query, *params = conn.fetch.await_args_list[0].args

        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["payments"][0]["subscriptionId"], 2)
        self.assertEqual(result["data"]["pagination"], {"limit": 30, "offset": 0})
        self.assertNotIn(" IS NULL OR ", query)
        self.assertIn("WHERE user_id = $1", query)
        self.assertIn("LIMIT $2 OFFSET $3", query)
        self.assertEqual(params, [4, 30, 0])

    async def test_get_user_payment_history_builds_query_with_all_filters(self):
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])

        await payment_history_service.get_user_payment_history(
            conn,
            4,
            2,
            date(2026, 1, 1),
            date(2026, 1, 31),
            10,
            5,
        )

        query, *params = conn.fetch.await_args_list[0].args

        self.assertNotIn(" IS NULL OR ", query)
        self.assertIn("WHERE user_id = $1 AND subscription_id = $2 AND paid_at >= $3 AND paid_at <= $4", query)
        self.assertIn("LIMIT $5 OFFSET $6", query)
        self.assertEqual(params, [4, 2, date(2026, 1, 1), date(2026, 1, 31), 10, 5])

    async def test_get_subscription_payment_history_returns_infrastructure_error_when_database_fails(self):
        conn = MagicMock()
        conn.fetch = AsyncMock(side_effect=RuntimeError("database unavailable"))

        result = await payment_history_service.get_subscription_payment_history(conn, 2, 4, 30, 0)

        self.assertEqual(result, {"status": False, "message": "An error occurred while fetching payment history", "data": {}})

    async def test_get_user_payment_history_returns_infrastructure_error_when_database_fails(self):
        conn = MagicMock()
        conn.fetch = AsyncMock(side_effect=RuntimeError("database unavailable"))

        result = await payment_history_service.get_user_payment_history(conn, 4, None, None, None, 30, 0)

        self.assertEqual(result, {"status": False, "message": "An error occurred while fetching payment history", "data": {}})
