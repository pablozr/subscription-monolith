import bcrypt
import jwt
from datetime import datetime, timedelta
from core.logger.logger import logger
from core.config.config import settings
from core.postgresql.postgresql import postgresql
from services.user.user_service import get_one_user


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
    expire = datetime.now() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
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

async def verify_token(token: str, check_can_update: bool = False) -> dict | bool | None:
    try:

        if token.startswith("Bearer "):
            token = token[7:]

        payload = decode_access_token(token)
        conn = postgresql.get_db()

        if payload["userId"]:
            response = await get_one_user(conn, payload["userId"])

            if response["status"] is None or not response["status"]:
                raise jwt.InvalidSignatureError("User not found")

            if check_can_update:
                if payload["canUpdate"]:
                    return response["data"]["user"]
                else:
                    raise jwt.InvalidTokenError("User does not have update permissions")
            return response["data"]["user"]
        else:
            raise jwt.InvalidTokenError("Invalid token payload")

    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token")
        return False