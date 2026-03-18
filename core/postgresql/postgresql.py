from typing import Optional
from core.config.config import settings
import asyncpg


class PostgreSQL:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.config = settings

    async def connect(self):
        dsn: str = f"postgresql://{self.config.DB_USER}:{self.config.DB_PASSWORD}@{self.config.DB_HOST}:{self.config.DB_PORT}/{self.config.DB_NAME}"
        self.pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=3)

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def get_db(self):
        if not self.pool:
            raise Exception("Database connection pool is not initialized.")

        async with self.pool.acquire() as conn:
            yield conn


postgresql = PostgreSQL()
