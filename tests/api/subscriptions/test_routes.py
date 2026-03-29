from unittest.mock import AsyncMock, patch

from tests.api.helpers import ApiBaseTestCase, TEST_DB_CONN


class SubscriptionApiTests(ApiBaseTestCase):
    def test_create_subscription_returns_201(self):
        with patch(
            "routes.subscription.router.subscription_service.create_subscription",
            new=AsyncMock(return_value={
                "status": True,
                "message": "Subscription created",
                "data": {"subscription": {"id": 7, "name": "Netflix"}},
            }),
        ) as mocked_create:
            response = self.client.post(
                "/subscriptions",
                json={
                    "name": "Netflix",
                    "price": 39.9,
                    "billingCycle": "MONTHLY",
                    "startDate": "2026-01-15",
                    "reminderDaysBefore": 3,
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["message"], "Subscription created")

        args = mocked_create.await_args_list[0].args
        self.assertIs(args[0], TEST_DB_CONN)
        self.assertEqual(args[1], 17)
        self.assertEqual(args[2].billing_cycle, "MONTHLY")

    def test_get_one_subscription_returns_400_for_business_error(self):
        with patch(
            "routes.subscription.router.subscription_service.get_one_subscription",
            new=AsyncMock(return_value={"status": False, "message": "Subscription not found", "data": {}}),
        ):
            response = self.client.get("/subscriptions/999")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Subscription not found"})

    def test_cancel_subscription_returns_success_payload(self):
        with patch(
            "routes.subscription.router.subscription_service.cancel_subscription",
            new=AsyncMock(return_value={
                "status": True,
                "message": "Subscription canceled",
                "data": {"subscription": {"id": 9, "status": "CANCELED"}},
            }),
        ) as mocked_cancel:
            response = self.client.patch("/subscriptions/9/cancel")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Subscription canceled")

        args = mocked_cancel.await_args_list[0].args
        self.assertIs(args[0], TEST_DB_CONN)
        self.assertEqual(args[1], 9)
        self.assertEqual(args[2], 17)

    def test_create_subscription_rejects_invalid_billing_cycle(self):
        with patch("routes.subscription.router.subscription_service.create_subscription", new=AsyncMock()) as mocked_create:
            response = self.client.post(
                "/subscriptions",
                json={
                    "name": "Netflix",
                    "price": 39.9,
                    "billingCycle": "INVALID",
                    "startDate": "2026-01-15",
                    "reminderDaysBefore": 3,
                },
            )

        self.assertEqual(response.status_code, 422)
        mocked_create.assert_not_awaited()
