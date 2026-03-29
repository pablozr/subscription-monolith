import json
import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64

from aio_pika import Message
from aio_pika.abc import AbstractIncomingMessage
from core.config.config import settings
from core.logger.logger import logger
from core.rabbitmq.rabbitmq import rabbitmq


def _extract_email_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}

    email_payload = payload.get("email")

    if isinstance(email_payload, dict):
        return email_payload

    return payload


def _get_retry_count(headers: dict | None) -> int:
    if not headers:
        return 0

    raw_retry_count = headers.get("x-retry-count")
    if raw_retry_count is None:
        raw_retry_count = headers.get(b"x-retry-count")

    if raw_retry_count is None:
        return 0

    if isinstance(raw_retry_count, bytes):
        raw_retry_count = raw_retry_count.decode("utf-8", errors="ignore")

    if not isinstance(raw_retry_count, (str, int)):
        return 0

    try:
        retry_count = int(raw_retry_count)
    except (TypeError, ValueError):
        return 0

    return max(retry_count, 0)


async def _publish_to_queue(payload: dict, queue_name: str, retry_count: int = 0):
    if not rabbitmq.channel:
        raise RuntimeError("RabbitMQ channel is not initialized")

    message = Message(
        body=json.dumps(payload).encode(),
        delivery_mode=2,
        headers={"x-retry-count": retry_count},
    )

    await rabbitmq.channel.default_exchange.publish(message, routing_key=queue_name)


def _send_email_sync(payload: dict):
    msg = MIMEMultipart()
    msg["From"] = payload.get("from", settings.EMAIL_FROM)
    msg["To"] = payload["to"]
    msg["Subject"] = payload["subject"]

    if payload.get("html"):
        msg.attach(MIMEText(payload["html"], "html"))
    elif payload.get("message"):
        msg.attach(MIMEText(payload["message"], "plain"))

    if payload.get("base64Attachment") and payload.get("base64AttachmentName"):
        attachment_data = base64.b64decode(payload["base64Attachment"])
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment_data)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition", f'attachment; filename="{payload["base64AttachmentName"]}"'
        )
        msg.attach(part)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS) as server:
        if settings.SMTP_USE_STARTTLS:
            context = ssl.create_default_context()
            server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(msg["From"], msg["To"], msg.as_string())


async def process_email(message: AbstractIncomingMessage):
    retry_count = _get_retry_count(message.headers)

    try:
        payload = json.loads(message.body.decode())
    except (UnicodeDecodeError, json.decoder.JSONDecodeError):
        logger.error("Invalid email payload. Sending to DLQ.")
        try:
            await _publish_to_queue(
                payload={
                    "error": "invalid_json_payload",
                    "rawBody": message.body.decode("utf-8", errors="replace"),
                },
                queue_name=settings.EMAIL_DLQ_NAME,
                retry_count=retry_count,
            )
            await message.ack()
        except Exception as e:
            logger.exception(f"Failed to send invalid payload to DLQ: {e}")
            await message.nack(requeue=True)
        return

    email_payload = _extract_email_payload(payload)

    email_to = email_payload.get("to")
    email_subject = email_payload.get("subject")
    if not email_to or not email_subject:
        logger.warning("Email payload missing required fields. Sending to DLQ.")
        try:
            await _publish_to_queue(
                payload={
                    "error": "missing_required_email_fields",
                    "payload": payload,
                },
                queue_name=settings.EMAIL_DLQ_NAME,
                retry_count=retry_count,
            )
            await message.ack()
        except Exception as e:
            logger.exception(f"Failed to send malformed payload to DLQ: {e}")
            await message.nack(requeue=True)
        return

    try:
        await asyncio.to_thread(_send_email_sync, email_payload)
        logger.info(f"Email sent to {email_to}")
        await message.ack()
    except Exception as e:
        logger.exception(f"Email delivery failed: {e}")

        if retry_count >= settings.EMAIL_QUEUE_MAX_RETRIES:
            try:
                await _publish_to_queue(
                    payload={
                        "error": "max_retries_exceeded",
                        "retryCount": retry_count,
                        "payload": payload,
                    },
                    queue_name=settings.EMAIL_DLQ_NAME,
                    retry_count=retry_count,
                )
                await message.ack()
                logger.error("Email moved to DLQ after max retries")
            except Exception as dlq_error:
                logger.exception(f"Failed to move email to DLQ: {dlq_error}")
                await message.nack(requeue=True)
            return

        next_retry = retry_count + 1
        try:
            await _publish_to_queue(
                payload=payload,
                queue_name=settings.EMAIL_RETRY_QUEUE_NAME,
                retry_count=next_retry,
            )
            await message.ack()
            logger.warning(f"Email queued for retry #{next_retry}")
        except Exception as retry_error:
            logger.exception(f"Failed to queue email retry: {retry_error}")
            await message.nack(requeue=True)


async def start_email_worker():
    await rabbitmq.connect()
    if not rabbitmq.channel:
        raise RuntimeError("RabbitMQ channel is not initialized")

    channel = rabbitmq.channel
    await channel.set_qos(prefetch_count=1)

    await channel.declare_queue(settings.EMAIL_DLQ_NAME, durable=True)
    await channel.declare_queue(
        settings.EMAIL_RETRY_QUEUE_NAME,
        durable=True,
        arguments={
            "x-message-ttl": settings.EMAIL_RETRY_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": settings.EMAIL_QUEUE_NAME,
        },
    )

    queue = await channel.declare_queue(settings.EMAIL_QUEUE_NAME, durable=True)

    logger.info("Email worker started, waiting for messages...")
    await queue.consume(process_email)

    try:
        await asyncio.Future()
    finally:
        await rabbitmq.disconnect()


if __name__ == "__main__":
    asyncio.run(start_email_worker())
