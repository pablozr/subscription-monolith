import asyncio
import json as jsonlib
from unittest import TestCase
from urllib.parse import urlencode

from fastapi import FastAPI

from core.postgresql.postgresql import postgresql
from core.rabbitmq.rabbitmq import rabbitmq
from core.redis.redis import redis_cache
from core.security import rate_limit, security
from routes.auth.router import router as auth_router
from routes.payment_history.router import router as payment_history_router
from routes.subscription.router import router as subscription_router
from routes.users.router import router as users_router


TEST_DB_CONN = object()
TEST_REDIS_CLIENT = object()
TEST_MQ_CHANNEL = object()
AUTH_USER = {"userId": 17, "email": "api@test.com", "role": "BASIC"}
RESET_USER = {"userId": 17, "email": "api@test.com", "canUpdate": True}


async def override_db():
    yield TEST_DB_CONN


async def override_redis():
    yield TEST_REDIS_CLIENT


async def override_mq_channel():
    yield TEST_MQ_CHANNEL


async def override_auth_user():
    return AUTH_USER


async def override_reset_user():
    return RESET_USER


async def bypass_rate_limit():
    return None


class ASGIResponse:
    def __init__(self, status_code: int, headers: list[tuple[bytes, bytes]], body: bytes):
        self.status_code = status_code
        self.body = body
        self.headers = {}

        for header_name, header_value in headers:
            name = header_name.decode("latin-1").lower()
            value = header_value.decode("latin-1")

            if name in self.headers:
                self.headers[name] = f"{self.headers[name]}, {value}"
            else:
                self.headers[name] = value

    def json(self):
        return jsonlib.loads(self.body.decode("utf-8"))

    def header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)


class ASGITestClient:
    def __init__(self, app: FastAPI):
        self.app = app

    def get(self, path: str, params: dict | None = None, headers: dict | None = None) -> ASGIResponse:
        return self.request("GET", path, params=params, headers=headers)

    def post(
        self,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> ASGIResponse:
        return self.request("POST", path, json_data=json, params=params, headers=headers)

    def put(
        self,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> ASGIResponse:
        return self.request("PUT", path, json_data=json, params=params, headers=headers)

    def patch(
        self,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> ASGIResponse:
        return self.request("PATCH", path, json_data=json, params=params, headers=headers)

    def request(
        self,
        method: str,
        path: str,
        json_data: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> ASGIResponse:
        return asyncio.run(self._request(method, path, json_data=json_data, params=params, headers=headers))

    async def _request(
        self,
        method: str,
        path: str,
        json_data: dict | None,
        params: dict | None,
        headers: dict | None,
    ) -> ASGIResponse:
        query_string = urlencode(params or {}, doseq=True)
        body = b""
        request_headers = [(b"host", b"testserver")]

        if json_data is not None:
            body = jsonlib.dumps(json_data).encode("utf-8")
            request_headers.append((b"content-type", b"application/json"))
            request_headers.append((b"content-length", str(len(body)).encode("ascii")))

        for key, value in (headers or {}).items():
            request_headers.append((key.lower().encode("latin-1"), str(value).encode("latin-1")))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("latin-1"),
            "query_string": query_string.encode("latin-1"),
            "headers": request_headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "state": {},
        }

        response_status = 500
        response_headers = []
        response_body = b""
        request_sent = False

        async def receive():
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            nonlocal response_status, response_headers, response_body
            if message["type"] == "http.response.start":
                response_status = message["status"]
                response_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")

        await self.app(scope, receive, send)
        return ASGIResponse(response_status, response_headers, response_body)


def build_test_client() -> ASGITestClient:
    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")
    app.include_router(users_router, prefix="/users")
    app.include_router(subscription_router, prefix="/subscriptions")
    app.include_router(payment_history_router, prefix="/payments")

    overrides = app.dependency_overrides
    overrides[postgresql.get_db] = override_db
    overrides[redis_cache.get_redis] = override_redis
    overrides[rabbitmq.get_channel] = override_mq_channel
    overrides[security.validate_token_wrapper] = override_auth_user
    overrides[security.validate_token_to_validate_code] = override_reset_user
    overrides[security.validate_token_to_update_password] = override_reset_user
    overrides[rate_limit.rate_limit_login] = bypass_rate_limit
    overrides[rate_limit.rate_limit_google_login] = bypass_rate_limit
    overrides[rate_limit.rate_limit_forget_password] = bypass_rate_limit
    overrides[rate_limit.rate_limit_validate_code] = bypass_rate_limit

    return ASGITestClient(app)


class ApiBaseTestCase(TestCase):
    def setUp(self):
        self.client = build_test_client()
