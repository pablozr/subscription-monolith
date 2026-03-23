import secrets
from datetime import timedelta

from schemas.auth import LoginRequestModel, LoginGoogleRequestModel, ForgetPasswordRequestModel
from core.security import security
from core.logger.logger import logger
from schemas.user import UserCreateRequest
from services.user import user_service
from functions.utils import utils
from services.cache import cache_service
from services.messaging import messaging_service
from templates.email import master_forget_password_email_template


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
                "role": user["role"],
                "type": "auth"
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
                password=secrets.token_urlsafe(32),
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
                "role": user["role"],
                "type": "auth"
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


async def forget_password(conn, clientmq, redis_client, data: ForgetPasswordRequestModel) -> dict:
    select_query = """
                   SELECT id, email
                   FROM users
                   WHERE email = $1 \
                   """

    try:
        row = await conn.fetchrow(select_query, data.email)

        if not row:
            return {"status": False, "message": "If the email exists, a reset code was sent"}

        code = utils.generate_temp_code()
        await cache_service.create_items_by_key(f"{row["id"]}:{data.email}", 600, {"code": code}, redis_client)

        payload = {
            "to": data.email,
            "from": "pablo@sla",
            "html": master_forget_password_email_template.replace('CODIGO_AQUI', code),
            "subject": 'Redefinição de Senha',
            "base64Attachment": '',
            "base64AttachmentName": '',
            "message": ''
        }

        await messaging_service.publish("email-queue", payload, clientmq)

        access_token = security.create_access_token(
            {
                "userId": row["id"],
                "email": row["email"],
                "canUpdate": False,
                "type": "reset"
            },
            expires_delta=timedelta(minutes=15)
        )

        return {
            "status": True,
            "message": "Email sent successfully ",
            "data": {
                "access_token": access_token,
            }
        }
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred during sending email "}
