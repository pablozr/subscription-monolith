import json
import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64

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
    async with message.process(requeue=True):
        try:
            payload = json.loads(message.body.decode())
        except json.decoder.JSONDecodeError:
            logger.error("Invalid email payload. Message ignored.")
            return

        email_payload = _extract_email_payload(payload)

        email_to = email_payload.get("to")
        email_subject = email_payload.get("subject")
        if not email_to or not email_subject:
            logger.warning("Email payload missing required fields. Message ignored.")
            return

        try:
            await asyncio.to_thread(_send_email_sync, email_payload)
            logger.info(f"Email sent to {email_to}")
        except Exception as e:
            logger.exception(f"Email delivery failed: {e}")
            raise


async def start_email_worker():
    await rabbitmq.connect()
    if not rabbitmq.channel:
        raise RuntimeError("RabbitMQ channel is not initialized")

    channel = rabbitmq.channel
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue(settings.EMAIL_QUEUE_NAME, durable=True)

    logger.info("Email worker started, waiting for messages...")
    await queue.consume(process_email)

    try:
        await asyncio.Future()
    finally:
        await rabbitmq.disconnect()


if __name__ == "__main__":
    asyncio.run(start_email_worker())
