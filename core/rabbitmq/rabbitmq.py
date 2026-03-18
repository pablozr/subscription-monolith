from aio_pika import connect_robust
from aio_pika.abc import AbstractChannel
from core.config.config import settings


class RabbitMQ:
    def __init__(self):
        self.connection = None
        self.channel: AbstractChannel | None = None
        self.config = settings

    async def connect(self):
        self.connection = await connect_robust(
            f"amqp://{self.config.RABBITMQ_USER}:{self.config.RABBITMQ_PASSWORD}@{self.config.RABBITMQ_HOST}:{self.config.RABBITMQ_PORT}/")
        self.channel = await self.connection.channel()

    async def disconnect(self):
        if self.channel:
            await self.channel.close()
        if self.connection:
            await self.connection.close()

    async def get_channel(self):
        if not self.connection or not self.channel:
            raise Exception("RabbitMQ connection is not initialized.")

        yield self.channel


rabbitmq = RabbitMQ()
