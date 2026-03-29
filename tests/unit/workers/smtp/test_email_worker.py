import json
from typing import Any, cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from core.config.config import settings
from workers.smtp import email_worker
from tests.unit.helpers import FakeIncomingMessage


class EmailWorkerTests(IsolatedAsyncioTestCase):
    def test_extract_email_payload_handles_nested_and_flat_payloads(self):
        self.assertEqual(email_worker._extract_email_payload({"email": {"to": "a@test.com"}}), {"to": "a@test.com"})
        self.assertEqual(email_worker._extract_email_payload({"to": "a@test.com"}), {"to": "a@test.com"})
        self.assertEqual(email_worker._extract_email_payload(cast(dict, "bad")), {})

    async def test_process_email_ignores_invalid_json_messages(self):
        message = FakeIncomingMessage(b"not-json")

        with patch("workers.smtp.email_worker.asyncio.to_thread", AsyncMock()) as to_thread, \
             patch("workers.smtp.email_worker._publish_to_queue", AsyncMock()) as publish_to_queue:
            await email_worker.process_email(cast(Any, message))

        to_thread.assert_not_awaited()
        publish_to_queue.assert_awaited_once()
        self.assertTrue(message.acked)

    async def test_process_email_sends_valid_payload_via_thread(self):
        payload = {"email": {"to": "user@test.com", "subject": "Hello", "message": "Hi", "from": "sender@test.com"}}
        message = FakeIncomingMessage(json.dumps(payload).encode())

        with patch("workers.smtp.email_worker.asyncio.to_thread", AsyncMock()) as to_thread:
            await email_worker.process_email(cast(Any, message))

        to_thread.assert_awaited_once_with(email_worker._send_email_sync, payload["email"])
        self.assertTrue(message.acked)

    async def test_process_email_queues_retry_on_delivery_failure(self):
        payload = {"email": {"to": "user@test.com", "subject": "Hello", "message": "Hi", "from": "sender@test.com"}}
        message = FakeIncomingMessage(json.dumps(payload).encode(), headers={"x-retry-count": 1})

        with patch("workers.smtp.email_worker.asyncio.to_thread", AsyncMock(side_effect=RuntimeError("smtp down"))), \
             patch("workers.smtp.email_worker._publish_to_queue", AsyncMock()) as publish_to_queue:
            await email_worker.process_email(cast(Any, message))

        publish_to_queue.assert_awaited_once_with(
            payload=payload,
            queue_name=settings.EMAIL_RETRY_QUEUE_NAME,
            retry_count=2,
        )
        self.assertTrue(message.acked)

    async def test_process_email_moves_message_to_dlq_after_max_retries(self):
        payload = {"email": {"to": "user@test.com", "subject": "Hello", "message": "Hi", "from": "sender@test.com"}}
        message = FakeIncomingMessage(
            json.dumps(payload).encode(),
            headers={"x-retry-count": settings.EMAIL_QUEUE_MAX_RETRIES},
        )

        with patch("workers.smtp.email_worker.asyncio.to_thread", AsyncMock(side_effect=RuntimeError("smtp down"))), \
             patch("workers.smtp.email_worker._publish_to_queue", AsyncMock()) as publish_to_queue:
            await email_worker.process_email(cast(Any, message))

        self.assertTrue(message.acked)
        self.assertEqual(publish_to_queue.await_count, 1)
        queue_name = publish_to_queue.await_args_list[0].kwargs["queue_name"]
        self.assertEqual(queue_name, settings.EMAIL_DLQ_NAME)
