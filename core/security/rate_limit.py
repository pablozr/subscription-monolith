from fastapi import Depends, HTTPException, Request
import redis.asyncio

from core.config.config import settings
from core.logger.logger import logger
from core.redis.redis import redis_cache


def get_client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


async def enforce_rate_limit(
    request: Request,
    redis_client: redis.asyncio.Redis,
    key_prefix: str,
    max_requests: int,
) -> None:
    if max_requests <= 0:
        return

    key = f"rate_limit:{key_prefix}:{get_client_identifier(request)}"

    try:
        current_attempts = await redis_client.incr(key)
        if current_attempts == 1:
            await redis_client.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)

        if current_attempts > max_requests:
            ttl = await redis_client.ttl(key)
            headers = {"Retry-After": str(ttl)} if ttl and ttl > 0 else None
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers=headers,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Rate limit check failed for '{key_prefix}': {e}")


async def rate_limit_login(
    request: Request,
    redis_client=Depends(redis_cache.get_redis),
) -> None:
    await enforce_rate_limit(
        request=request,
        redis_client=redis_client,
        key_prefix="auth:login",
        max_requests=settings.RATE_LIMIT_LOGIN_MAX_REQUESTS,
    )


async def rate_limit_google_login(
    request: Request,
    redis_client=Depends(redis_cache.get_redis),
) -> None:
    await enforce_rate_limit(
        request=request,
        redis_client=redis_client,
        key_prefix="auth:google-login",
        max_requests=settings.RATE_LIMIT_GOOGLE_LOGIN_MAX_REQUESTS,
    )


async def rate_limit_forget_password(
    request: Request,
    redis_client=Depends(redis_cache.get_redis),
) -> None:
    await enforce_rate_limit(
        request=request,
        redis_client=redis_client,
        key_prefix="auth:forget-password",
        max_requests=settings.RATE_LIMIT_FORGET_PASSWORD_MAX_REQUESTS,
    )


async def rate_limit_validate_code(
    request: Request,
    redis_client=Depends(redis_cache.get_redis),
) -> None:
    await enforce_rate_limit(
        request=request,
        redis_client=redis_client,
        key_prefix="auth:validate-code",
        max_requests=settings.RATE_LIMIT_VALIDATE_CODE_MAX_REQUESTS,
    )
