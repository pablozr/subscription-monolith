import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from core.logger.logger import logger
from core.config.config import settings
from core.postgresql.postgresql import postgresql
from services.user import user_service
from fastapi import Request, HTTPException, Depends
from google.oauth2 import id_token
from google.auth.transport import requests


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False

    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.exception(e)
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        return None
    except jwt.InvalidTokenError:
        logger.error("Invalid token")
        return None


def verify_google_token(token: str) -> dict | None:
    try:
        user = id_token.verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)

        return {**user}
    except ValueError:
        logger.error("Invalid Google token")
        return None


async def verify_token(token: str, conn, check_can_update: bool = False) -> dict | bool | None:
    try:

        if token.startswith("Bearer "):
            token = token[7:]

        payload = decode_access_token(token)

        if payload["userId"]:
            response = await user_service.get_one_user(conn, payload["userId"])

            if response["status"] is None or not response["status"]:
                raise jwt.InvalidSignatureError("User not found")

            if check_can_update:
                if payload["canUpdate"]:
                    return dict(response["data"]["user"])
                else:
                    raise jwt.InvalidTokenError("User does not have update permissions")
            return dict(response["data"]["user"])
        else:
            raise jwt.InvalidTokenError("Invalid token payload")

    # I use None to represent expired, and False to invalid *
    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        return None
    except jwt.InvalidTokenError:
        logger.error(f"Invalid token")
        return False


async def validate_token(request: Request, conn, check_can_update: bool = False, reset_cookie: bool = False) -> dict:
    try:
        cookie_key = "auth" if not reset_cookie else "auth_reset"
        token = request.cookies.get(cookie_key)

        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        user = await verify_token(token, conn=conn, check_can_update=check_can_update)

        # I use None to represent expired, and False to invalid **
        if user is None:
            raise HTTPException(status_code=401, detail="Token has expired")
        if not user:
            raise HTTPException(status_code=401, detail="Invalid token")

        request.state.token = token

        return user

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=401, detail="Invalid token")


# Validates the token right before the user actually changes their password.
# It strictly requires the 'canUpdate' permission (proving they passed the code validation step)
# and passes reset_cookie=True to look for the reset_auth key

async def validate_token_to_update_password(request: Request, conn=Depends(postgresql.get_db)) -> dict:
    return await validate_token(request, conn, check_can_update=True, reset_cookie=True)


# Validates the token during the email code verification step.
# We don't require the 'canUpdate' permission here because the user is just proving they own the email.
# We pass reset_cookie=True to generate a new, temporary token (which will grant the 'canUpdate' permission for the final step).

async def validate_token_to_validate_code(request: Request, conn=Depends(postgresql.get_db)) -> dict:
    return await validate_token(request, conn, check_can_update=False, reset_cookie=True)


async def validate_token_wrapper(request: Request, conn=Depends(postgresql.get_db)) -> dict:
    return await validate_token(request, conn)


# ==========================================================
# JUST IN CASE IN THE FUTURE I NEED TO CONTROL ROLE ACCESS
# ==========================================================

def require_minimum_rank(minimum_rank: int):
    async def decorator(user: dict = Depends(validate_token_wrapper)):
        role_ranks = {
            "BASIC": 1,
            "ADMIN": 2
        }

        user_role = user.get("role", "").upper()
        rank = role_ranks.get(user_role, 0)

        if rank < minimum_rank:
            raise HTTPException(status_code=403, detail="User doesn't have enough rank")

        return user

    return decorator


# Here I could have used the wrapper, like I did before with validate_token, or I can use decorator functions

def require_admin_rank():
    return require_minimum_rank(2)
