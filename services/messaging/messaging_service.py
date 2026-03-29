import json
import aio_pika
from aio_pika import Message
from core.config.config import settings


async def publish(queue_name: str, payload: dict, channel: aio_pika.abc.AbstractChannel):
    await channel.declare_queue(queue_name, durable=True)

    message = Message(
        body=json.dumps(payload).encode(),
        delivery_mode=2
    )

    await channel.default_exchange.publish(message, routing_key=queue_name)


async def publish_notification(payload: dict, channel: aio_pika.abc.AbstractChannel):
    await publish(settings.EMAIL_QUEUE_NAME, payload, channel)
