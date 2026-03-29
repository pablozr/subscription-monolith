from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.user import UserCreateRequest, UserUpdateRequest
from services.user import user_service
from tests.unit.helpers import AsyncContextManager


class UserServiceTests(IsolatedAsyncioTestCase):
    async def test_create_user_hashes_password_and_returns_public_payload(self):
        conn = MagicMock()
        conn.transaction.return_value = AsyncContextManager()
        conn.fetchrow = AsyncMock(return_value={"id": 7, "email": "user@test.com", "fullname": "Test User", "role": "BASIC"})

        with patch("services.user.user_service.security.hash_password", return_value="hashed-password") as hash_password:
            result = await user_service.create_user(
                conn,
                UserCreateRequest(email="user@test.com", password="12345678", fullName="Test User"),
            )

        hash_password.assert_called_once_with("12345678")
        conn.fetchrow.assert_awaited_once()
        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["user"]["userId"], 7)
        self.assertNotIn("password", result["data"]["user"])

    async def test_update_user_auto_rejects_empty_payload(self):
        conn = MagicMock()

        result = await user_service.update_user_auto(conn, 7, UserUpdateRequest())

        self.assertEqual(result, {"status": False, "message": "No fields to update", "data": {}})

    async def test_update_password_returns_not_found_when_user_missing(self):
        conn = MagicMock()
        conn.transaction.return_value = AsyncContextManager()
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("services.user.user_service.security.hash_password", return_value="hashed-password"):
            result = await user_service.update_password(conn, 77, "new-password")

        self.assertEqual(result, {"status": False, "message": "User not found", "data": {}})
