from datetime import date
from unittest.mock import AsyncMock, patch

from tests.api.helpers import ApiBaseTestCase, TEST_DB_CONN


class PaymentHistoryApiTests(ApiBaseTestCase):
    def test_create_payment_returns_201(self):
        with patch(
            "routes.payment_history.router.payment_history_service.create_payment",
            new=AsyncMock(return_value={
                "status": True,
                "message": "Payment created",
                "data": {"payment": {"id": 1}},
            }),
        ) as mocked_create:
            response = self.client.post(
                "/payments/subscriptions/10",
                json={"paymentMethod": "pix", "reference": "ref-1", "notes": "ok"},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["message"], "Payment created")

        args = mocked_create.await_args_list[0].args
        self.assertIs(args[0], TEST_DB_CONN)
        self.assertEqual(args[1], 10)
        self.assertEqual(args[2], 17)

    def test_get_subscription_payment_history_validates_limit(self):
        with patch(
            "routes.payment_history.router.payment_history_service.get_subscription_payment_history",
            new=AsyncMock(),
        ) as mocked_get_history:
            response = self.client.get("/payments/subscriptions/10", params={"limit": 201})

        self.assertEqual(response.status_code, 422)
        mocked_get_history.assert_not_awaited()

    def test_get_user_payment_history_rejects_inverted_dates(self):
        response = self.client.get(
            "/payments/history",
            params={"startDate": "2026-02-01", "endDate": "2026-01-01"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "startDate cannot be greater than endDate"})

    def test_get_user_payment_history_forwards_filters(self):
        with patch(
            "routes.payment_history.router.payment_history_service.get_user_payment_history",
            new=AsyncMock(return_value={
                "status": True,
                "message": "Payments fetched",
                "data": {"payments": [], "pagination": {"limit": 10, "offset": 5}},
            }),
        ) as mocked_get_history:
            response = self.client.get(
                "/payments/history",
                params={
                    "subscriptionId": 4,
                    "startDate": "2026-01-01",
                    "endDate": "2026-01-31",
                    "limit": 10,
                    "offset": 5,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Payments fetched")

        args = mocked_get_history.await_args_list[0].args
        self.assertIs(args[0], TEST_DB_CONN)
        self.assertEqual(args[1], 17)
        self.assertEqual(args[2], 4)
        self.assertEqual(args[3], date(2026, 1, 1))
        self.assertEqual(args[4], date(2026, 1, 31))
        self.assertEqual(args[5], 10)
        self.assertEqual(args[6], 5)
