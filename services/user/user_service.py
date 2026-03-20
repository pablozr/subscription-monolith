from schemas.user import UserGetResponse, UserCreateRequest
from core.security import security
from core.logger.logger import logger


async def get_one_user(conn, user_id: int) -> UserGetResponse:
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


async def create_user(conn, data: UserCreateRequest) -> dict:
    insert_query = """
                    INSERT INTO users (email, password, fullname, role, created_at)
                    VALUES ($1, $2, $3, 'BASIC', NOW())
                    RETURNING id, email, fullname, role
                   """

    try:
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
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while creating user"}