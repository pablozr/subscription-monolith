import json
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from workers.smtp import email_worker
from tests.unit.helpers import FakeIncomingMessage


class EmailWorkerTests(IsolatedAsyncioTestCase):
    def test_extract_email_payload_handles_nested_and_flat_payloads(self):
        self.assertEqual(email_worker._extract_email_payload({"email": {"to": "a@test.com"}}), {"to": "a@test.com"})
        self.assertEqual(email_worker._extract_email_payload({"to": "a@test.com"}), {"to": "a@test.com"})
        self.assertEqual(email_worker._extract_email_payload("bad"), {})

    async def test_process_email_ignores_invalid_json_messages(self):
        message = FakeIncomingMessage(b"not-json")

        with patch("workers.smtp.email_worker.asyncio.to_thread", AsyncMock()) as to_thread:
            await email_worker.process_email(message)

        to_thread.assert_not_awaited()

    async def test_process_email_sends_valid_payload_via_thread(self):
        payload = {"email": {"to": "user@test.com", "subject": "Hello", "message": "Hi", "from": "sender@test.com"}}
        message = FakeIncomingMessage(json.dumps(payload).encode())

        with patch("workers.smtp.email_worker.asyncio.to_thread", AsyncMock()) as to_thread:
            await email_worker.process_email(message)

        to_thread.assert_awaited_once_with(email_worker._send_email_sync, payload["email"])
