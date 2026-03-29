from unittest.mock import AsyncMock, patch

from tests.api.helpers import ApiBaseTestCase, TEST_DB_CONN


class UsersApiTests(ApiBaseTestCase):
    def test_get_me_returns_authenticated_user_payload(self):
        with patch(
            "routes.users.router.user_service.get_one_user",
            new=AsyncMock(return_value={
                "status": True,
                "message": "User fetched",
                "data": {"user": {"userId": 17, "email": "api@test.com"}},
            }),
        ) as mocked_get_user:
            response = self.client.get("/users/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["user"]["userId"], 17)

        args = mocked_get_user.await_args_list[0].args
        self.assertIs(args[0], TEST_DB_CONN)
        self.assertEqual(args[1], 17)

    def test_create_user_returns_201(self):
        with patch(
            "routes.users.router.user_service.create_user",
            new=AsyncMock(return_value={
                "status": True,
                "message": "User created",
                "data": {"user": {"userId": 33}},
            }),
        ) as mocked_create:
            response = self.client.post(
                "/users",
                json={
                    "email": "new-user@test.com",
                    "password": "12345678",
                    "fullName": "New Test User",
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"message": "User created", "data": {"user": {"userId": 33}}})

        args = mocked_create.await_args_list[0].args
        self.assertIs(args[0], TEST_DB_CONN)
        self.assertEqual(args[1].email, "new-user@test.com")

    def test_update_me_rejects_short_fullname(self):
        with patch("routes.users.router.user_service.update_user_auto", new=AsyncMock()) as mocked_update:
            response = self.client.put("/users/me", json={"fullname": "short"})

        self.assertEqual(response.status_code, 422)
        mocked_update.assert_not_awaited()
