import redis.asyncio
from core.config.config import settings


class Redis:
    def __init__(self, host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0):
        self.redis = None
        self.host = host
        self.port = port
        self.db = db

    async def connect(self):
        if self.redis is None:
            self.redis = redis.asyncio.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=settings.REDIS_PASSWORD,
                decode_responses=True
            )

    async def disconnect(self):
        if self.redis:
            await self.redis.aclose()

    async def get_redis(self):
        if self.redis is None:
            raise Exception("Redis connection is not initialized.")

        yield self.redis


redis_cache = Redis()
