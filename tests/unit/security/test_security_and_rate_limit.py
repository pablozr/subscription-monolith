import jwt
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from starlette.requests import Request

from core.security import rate_limit, security


def build_request(headers=None, cookies=None, client_host="127.0.0.1"):
    return Request({
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (client_host, 1234),
        "path": "/",
        "method": "GET",
    })


class SecurityTests(IsolatedAsyncioTestCase):
    async def test_verify_token_returns_none_for_expired_token(self):
        with patch("core.security.security.decode_access_token", side_effect=jwt.ExpiredSignatureError), \
             patch("core.security.security.user_service.get_one_user", AsyncMock()):
            result = await security.verify_token("token", conn=object())

        self.assertIsNone(result)

    async def test_validate_token_raises_when_cookie_missing(self):
        request = build_request()

        with self.assertRaises(HTTPException) as ctx:
            await security.validate_token(request, conn=object())

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Not authenticated")

    async def test_validate_token_reads_reset_cookie(self):
        request = build_request(headers={"cookie": "auth_reset=reset-token"})

        with patch("core.security.security.verify_token", AsyncMock(return_value={"userId": 1, "email": "user@test.com"})):
            user = await security.validate_token(request, conn=object(), reset_cookie=True, expected_type="reset")

        self.assertEqual(user["userId"], 1)
        self.assertEqual(request.state.token, "reset-token")


class RateLimitTests(IsolatedAsyncioTestCase, TestCase):
    def test_get_client_identifier_prefers_forwarded_for_header(self):
        request = build_request(headers={"x-forwarded-for": "10.0.0.1, 10.0.0.2"}, client_host="127.0.0.1")

        self.assertEqual(rate_limit.get_client_identifier(request), "10.0.0.1")

    async def test_enforce_rate_limit_sets_window_on_first_attempt(self):
        request = build_request()
        redis_client = SimpleNamespace(incr=AsyncMock(return_value=1), expire=AsyncMock(), ttl=AsyncMock(return_value=60))

        await rate_limit.enforce_rate_limit(request, redis_client, "auth:login", 5)

        redis_client.expire.assert_awaited_once()

    async def test_enforce_rate_limit_raises_with_retry_after_header(self):
        request = build_request()
        redis_client = SimpleNamespace(incr=AsyncMock(return_value=6), expire=AsyncMock(), ttl=AsyncMock(return_value=42))

        with self.assertRaises(HTTPException) as ctx:
            await rate_limit.enforce_rate_limit(request, redis_client, "auth:login", 5)

        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(ctx.exception.headers, {"Retry-After": "42"})
