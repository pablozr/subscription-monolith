from unittest.mock import AsyncMock, patch

from tests.api.helpers import (
    ApiBaseTestCase,
    RESET_USER,
    TEST_DB_CONN,
    TEST_MQ_CHANNEL,
    TEST_REDIS_CLIENT,
)


class AuthApiTests(ApiBaseTestCase):
    def test_login_sets_auth_cookie_and_hides_access_token(self):
        service_response = {
            "status": True,
            "message": "Login successful",
            "data": {
                "access_token": "jwt-token",
                "user": {"userId": 17, "email": "api@test.com"},
            },
        }

        with patch("routes.auth.router.auth_service.login", new=AsyncMock(return_value=service_response)) as mocked_login:
            response = self.client.post(
                "/auth/login",
                json={"email": "api@test.com", "password": "12345678"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "message": "Login successful",
                "data": {"user": {"userId": 17, "email": "api@test.com"}},
            },
        )
        cookie_header = response.header("set-cookie")
        self.assertIn("auth=jwt-token", cookie_header)
        self.assertIn("Max-Age=259200", cookie_header)
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("Secure", cookie_header)

        args = mocked_login.await_args_list[0].args
        self.assertIs(args[0], TEST_DB_CONN)
        self.assertEqual(args[1].email, "api@test.com")

    def test_login_returns_400_when_service_rejects_credentials(self):
        with patch(
            "routes.auth.router.auth_service.login",
            new=AsyncMock(return_value={"status": False, "message": "Invalid credentials", "data": {}}),
        ):
            response = self.client.post(
                "/auth/login",
                json={"email": "api@test.com", "password": "wrong"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Invalid credentials"})

    def test_forget_password_sets_reset_cookie_on_success(self):
        with patch(
            "routes.auth.router.auth_service.forget_password",
            new=AsyncMock(return_value={
                "status": True,
                "message": "Code sent",
                "data": {"access_token": "reset-token"},
            }),
        ) as mocked_forget:
            response = self.client.post("/auth/forget-password", json={"email": "api@test.com"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Code sent"})
        cookie_header = response.header("set-cookie")
        self.assertIn("auth_reset=reset-token", cookie_header)
        self.assertIn("Max-Age=900", cookie_header)

        args = mocked_forget.await_args_list[0].args
        self.assertIs(args[0], TEST_DB_CONN)
        self.assertIs(args[1], TEST_MQ_CHANNEL)
        self.assertIs(args[2], TEST_REDIS_CLIENT)
        self.assertEqual(args[3].email, "api@test.com")

    def test_validate_code_returns_400_when_code_is_invalid(self):
        with patch(
            "routes.auth.router.auth_service.validate_code",
            new=AsyncMock(return_value={"status": False, "message": "Invalid code", "data": {}}),
        ) as mocked_validate:
            response = self.client.post("/auth/validate-code", json={"code": "111111"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Invalid code"})

        args = mocked_validate.await_args_list[0].args
        self.assertIs(args[0], TEST_REDIS_CLIENT)
        self.assertEqual(args[1], "111111")
        self.assertEqual(args[2], RESET_USER)

    def test_update_password_deletes_reset_cookie(self):
        with patch(
            "routes.auth.router.user_service.update_password",
            new=AsyncMock(return_value={"status": True, "message": "Password updated", "data": {}}),
        ) as mocked_update:
            response = self.client.post("/auth/update-password", json={"password": "new-password"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Password updated"})
        cookie_header = response.header("set-cookie")
        self.assertIn("auth_reset=", cookie_header)
        self.assertIn("Max-Age=0", cookie_header)

        args = mocked_update.await_args_list[0].args
        self.assertIs(args[0], TEST_DB_CONN)
        self.assertEqual(args[1], 17)
        self.assertEqual(args[2], "new-password")

    def test_logout_deletes_auth_cookie(self):
        response = self.client.post("/auth/logout")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Successfully logged out"})
        cookie_header = response.header("set-cookie")
        self.assertIn("auth=", cookie_header)
        self.assertIn("Max-Age=0", cookie_header)
