from schemas.auth import LoginRequestModel
from core.security import security
from core.logger.logger import logger


async def login(conn, login_data: LoginRequestModel) -> dict:
    select_query = """
        SELECT id, email, fullname, role, password_hash FROM users WHERE email = $1
    """

    try:
        user = await conn.fetchrow(select_query, login_data.email)

        if not user:
            return {"status": False, "message": "Invalid email or password"}

        if not security.verify_password(login_data.password, user["password_hash"]):
            return {"status": False, "message": "Invalid email or password"}

        access_token = security.create_access_token(
            {
                "userId": user["id"],
                "email": user["email"],
                "fullname": user["fullname"],
                "role": user["role"]
            }
        )

        return {
            "status": True,
            "message": "Login successful",
            "data": {
                "access_token": access_token,
                "user": {
                    "userId": user["id"],
                    "email": user["email"],
                    "fullname": user["fullname"],
                    "role": user["role"]
                }
            }
        }

    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred during login"}
