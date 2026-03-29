import json
import redis.asyncio


async def get_items_by_key(key: str, redis_client: redis.asyncio.Redis) -> dict | None:
    raw_history = await redis_client.get(key)

    if raw_history:
        try:
            return json.loads(raw_history)
        except json.decoder.JSONDecodeError:
            return None
    return None


async def create_items_by_key(key: str, time: int, item: dict, redis_client: redis.asyncio.Redis) -> None:
    await redis_client.setex(key, time, json.dumps(item, default=str))


async def clear_items_by_key(key: str, redis_client: redis.asyncio.Redis) -> None:
    await redis_client.delete(key)
