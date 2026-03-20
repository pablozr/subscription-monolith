from schemas.auth import LoginRequestModel, LoginGoogleRequestModel
from core.security import security
from core.logger.logger import logger
from schemas.user import UserCreateRequest
from services.user import user_service


async def login(conn, login_data: LoginRequestModel) -> dict:
    select_query = """
                   SELECT id, email, fullname, role, password
                   FROM users
                   WHERE email = $1 \
                   """

    try:
        user = await conn.fetchrow(select_query, login_data.email)

        if not user:
            return {"status": False, "message": "Invalid email or password"}

        if not security.verify_password(login_data.password, user["password"]):
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


async def google_login(conn, data: LoginGoogleRequestModel) -> dict:
    select_query = """
                   SELECT id, email, fullname, role
                   FROM users
                   WHERE email = $1 \
                   """

    try:
        google_user = security.verify_google_token(data.token)

        if not google_user:
            return {"status": False, "message": "Invalid token"}

        user = await conn.fetchrow(select_query, google_user["email"])

        if not user:
            new_user = UserCreateRequest(
                email=google_user["email"],
                password=google_user["sub"],
                fullname=google_user["name"]
            )

            response = await user_service.create_user(conn, new_user)

            if not response["status"]:
                return {"status": False, "message": "Failed to create user"}

            new_user_data = response["data"]["user"]

            user = {
                "id": new_user_data["userId"],
                "email": new_user_data["email"],
                "fullname": new_user_data["fullname"],
                "role": new_user_data["role"]
            }

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
