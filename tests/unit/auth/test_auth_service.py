from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.auth import ForgetPasswordRequestModel, LoginGoogleRequestModel, LoginRequestModel
from services.auth import auth_service


class AuthServiceTests(IsolatedAsyncioTestCase):
    async def test_login_returns_token_and_user_on_valid_credentials(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={
            "id": 1,
            "email": "user@test.com",
            "fullname": "Test User",
            "role": "BASIC",
            "password": "hashed",
        })

        with patch("services.auth.auth_service.security.verify_password", return_value=True), \
             patch("services.auth.auth_service.security.create_access_token", return_value="jwt-token"):
            result = await auth_service.login(conn, LoginRequestModel(email="user@test.com", password="12345678"))

        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["access_token"], "jwt-token")
        self.assertEqual(result["data"]["user"]["email"], "user@test.com")

    async def test_google_login_creates_user_when_email_does_not_exist(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        created_user = {"userId": 9, "email": "google@test.com", "fullname": "Google User", "role": "BASIC"}

        with patch("services.auth.auth_service.security.verify_google_token", return_value={"email": "google@test.com", "name": "Google User"}), \
             patch("services.auth.auth_service.user_service.create_user", AsyncMock(return_value={"status": True, "data": {"user": created_user}})), \
             patch("services.auth.auth_service.security.create_access_token", return_value="jwt-token"):
            result = await auth_service.google_login(conn, LoginGoogleRequestModel(token="good-token"))

        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["user"], created_user)

    async def test_forget_password_stores_code_queues_email_and_returns_reset_token(self):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"id": 12, "email": "user@test.com"})

        with patch("services.auth.auth_service.utils.generate_temp_code", return_value="123456"), \
             patch("services.auth.auth_service.cache_service.create_items_by_key", AsyncMock()) as create_items, \
             patch("services.auth.auth_service.messaging_service.publish_notification", AsyncMock()) as publish_notification, \
             patch("services.auth.auth_service.security.create_access_token", return_value="reset-token"):
            result = await auth_service.forget_password(
                conn,
                clientmq=object(),
                redis_client=object(),
                data=ForgetPasswordRequestModel(email="user@test.com"),
            )

        create_items.assert_awaited_once()
        publish_notification.assert_awaited_once()
        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["access_token"], "reset-token")

    async def test_validate_code_clears_cache_and_returns_upgrade_token(self):
        redis_client = object()

        with patch("services.auth.auth_service.cache_service.get_items_by_key", AsyncMock(return_value={"code": "123456"})), \
             patch("services.auth.auth_service.cache_service.clear_items_by_key", AsyncMock()) as clear_items, \
             patch("services.auth.auth_service.security.create_access_token", return_value="validated-token"):
            result = await auth_service.validate_code(redis_client, "123456", {"userId": 2, "email": "user@test.com"})

        clear_items.assert_awaited_once_with("2:user@test.com", redis_client)
        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["access_token"], "validated-token")

    async def test_validate_code_rejects_wrong_code(self):
        with patch("services.auth.auth_service.cache_service.get_items_by_key", AsyncMock(return_value={"code": "999999"})):
            result = await auth_service.validate_code(object(), "123456", {"userId": 2, "email": "user@test.com"})

        self.assertEqual(result, {"status": False, "message": "Invalid code", "data": {}})
