from datetime import date
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock

from schemas.subscription import SubscriptionCreateRequest, SubscriptionUpdateRequest
from services.subscription import subscription_service
from tests.unit.helpers import AsyncContextManager


class SubscriptionCalculationTests(TestCase):
    def test_calculate_next_payment_uses_billing_cycle_offsets(self):
        start = date(2026, 1, 31)

        self.assertEqual(subscription_service.calculate_next_payment(start, "WEEKLY"), date(2026, 2, 7))
        self.assertEqual(subscription_service.calculate_next_payment(start, "MONTHLY"), date(2026, 2, 28))
        self.assertEqual(subscription_service.calculate_next_payment(start, "YEARLY"), date(2027, 1, 31))


class SubscriptionServiceTests(IsolatedAsyncioTestCase):
    async def test_create_subscription_calculates_next_payment_and_formats_response(self):
        conn = MagicMock()
        conn.transaction.return_value = AsyncContextManager()
        conn.fetchrow = AsyncMock(return_value={
            "id": 9,
            "user_id": 4,
            "name": "Netflix",
            "price": Decimal("39.90"),
            "billing_cycle": "MONTHLY",
            "status": "ACTIVE",
            "start_date": date(2026, 1, 15),
            "next_payment_date": date(2026, 2, 15),
            "reminder_days_before": 3,
        })
        payload = SubscriptionCreateRequest(
            name="Netflix",
            price=39.9,
            billingCycle="MONTHLY",
            startDate=date(2026, 1, 15),
            reminderDaysBefore=3,
        )

        result = await subscription_service.create_subscription(conn, 4, payload)

        args = conn.fetchrow.await_args.args
        self.assertEqual(args[1:], (4, "Netflix", 39.9, "MONTHLY", date(2026, 1, 15), date(2026, 2, 15), 3))
        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["subscription"]["price"], 39.9)
        self.assertEqual(result["data"]["subscription"]["next_payment_date"], "2026-02-15")

    async def test_update_subscription_rejects_empty_payload(self):
        conn = MagicMock()

        result = await subscription_service.update_subscription(conn, 10, 4, SubscriptionUpdateRequest())

        self.assertEqual(result, {"status": False, "message": "No fields to update", "data": {}})

    async def test_cancel_subscription_reports_missing_or_already_canceled_subscription(self):
        conn = MagicMock()
        conn.transaction.return_value = AsyncContextManager()
        conn.fetchrow = AsyncMock(return_value=None)

        result = await subscription_service.cancel_subscription(conn, 10, 4)

        self.assertEqual(result, {"status": False, "message": "Subscription not found or already canceled", "data": {}})

    async def test_get_all_subscriptions_orders_and_formats_rows(self):
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[{
            "id": 1,
            "user_id": 4,
            "name": "Spotify",
            "price": Decimal("21.50"),
            "billing_cycle": "MONTHLY",
            "status": "ACTIVE",
            "start_date": date(2026, 1, 10),
            "next_payment_date": date(2026, 2, 10),
            "reminder_days_before": 5,
            "canceled_at": None,
        }])

        result = await subscription_service.get_all_subscriptions(conn, 4)

        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["subscriptions"][0]["price"], 21.5)
        self.assertIsNone(result["data"]["subscriptions"][0]["canceled_at"])
