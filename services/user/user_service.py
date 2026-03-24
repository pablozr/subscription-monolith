import asyncpg
from asyncpg.exceptions import UniqueViolationError

from schemas.user import UserGetResponse, UserCreateRequest
from core.security import security
from core.logger.logger import logger


async def get_one_user(conn: asyncpg.Connection, user_id: int) -> UserGetResponse:
    query = "SELECT id, email FROM users WHERE id = $1"

    row = await conn.fetchrow(query, user_id)

    if not row:
        return {"status": False, "message": "User not found", "data": dict()}

    return {
        "status": True,
        "message": "User retrieved successfully",
        "data": {
            "user": {
                "user_id": row["id"],
                "email": row["email"]
            }
        }
    }


async def create_user(conn: asyncpg.Connection, data: UserCreateRequest) -> dict:
    insert_query = """
                   INSERT INTO users (email, password, fullname, role, created_at)
                   VALUES ($1, $2, $3, 'BASIC', NOW()) RETURNING id, email, fullname, role
                   """

    try:
        async with conn.transaction():

            hashed_password = security.hash_password(data.password)

            response = await conn.fetchrow(insert_query, data.email, hashed_password, data.fullname)

            if not response:
                return {"status": False, "message": "Failed to create user"}

            return {"status": True, "message": "User created successfully", "data": {
                "user": {
                    "userId": response["id"],
                    "email": response["email"],
                    "fullname": response["fullname"],
                    "role": response["role"]
                }
            }}
    except UniqueViolationError:
        return {"status": False, "message": "Email already in use", "data": {}}
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while creating user"}


async def update_user_auto(conn: asyncpg.Connection, user_id: int, data: dict) -> dict:
    allowed_columns = {"fullname", "email"}
    filtered = {k: v for k, v in data.items(
    ) if k in allowed_columns and v is not None}

    if not filtered:
        return {"status": False, "message": "No fields to update", "data": {}}

    columns = list(filtered.keys())
    values = list(filtered.values())
    set_clause = ", ".join(f"{col} = ${i}" for i, col in enumerate(columns, 1))
    values.append(user_id)

    update_query = f"UPDATE users SET {set_clause}, updated_at = NOW() WHERE id = ${len(values)} RETURNING id, email, fullname, role"

    try:
        async with conn.transaction():
            response = await conn.fetchrow(update_query, *values)

            if not response:
                return {"status": False, "message": "Failed to update user", "data": {}}

            return {
                "status": True,
                "message": "User updated successfully",
                "data": {"user": response}
            }
    except UniqueViolationError:
        return {"status": False, "message": "Email already in use", "data": {}}
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while updating user", "data": {}}


async def update_password(conn: asyncpg.Connection, user_id: int, new_password: str) -> dict:
    update_query = """
                   UPDATE users SET password = $1, updated_at = NOW()
                   WHERE id = $2
                   """

    try:
        async with conn.transaction():
            hashed_password = security.hash_password(new_password)
            await conn.execute(update_query, hashed_password, user_id)

            return {"status": True, "message": "Password updated successfully", "data": {}}
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while updating password", "data": {}}
