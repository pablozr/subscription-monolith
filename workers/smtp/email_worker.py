import json
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import base64

from aio_pika import IncomingMessage
from core.config.config import settings
from core.logger.logger import logger
from core.rabbitmq.rabbitmq import rabbitmq


async def process_email(message: IncomingMessage):
    async with message.process():
        try:
            payload = json.loads(message.body.decode())

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
                    "Content-Disposition", f'attachment; filename="{payload["base64AttachmentName"]}"')
                msg.attach(part)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], msg["To"], msg.as_string())

            logger.info(f"Email sent to {payload['to']}")

        except Exception as e:
            logger.exception(e)


async def start_email_worker():
    await rabbitmq.connect()
    await rabbitmq.channel.set_qos(prefetch_count=1)

    queue = await rabbitmq.channel.declare_queue("email-queue", durable=True)

    logger.info("Email worker started, waiting for messages...")
    await queue.consume(process_email)

    try:
        await asyncio.Future()
    finally:
        await rabbitmq.disconnect()


if __name__ == "__main__":
    asyncio.run(start_email_worker())
