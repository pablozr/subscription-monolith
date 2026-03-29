from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse
from core.logger.logger import logger
from schemas.auth import LoginRequestModel, LoginGoogleRequestModel, ForgetPasswordRequestModel, ValidateCodeRequest, UpdatePasswordRequest
from services.auth import auth_service
from services.user import user_service
from core.postgresql.postgresql import postgresql
from core.security import security, rate_limit
from core.rabbitmq.rabbitmq import rabbitmq
from core.redis.redis import redis_cache


router = APIRouter()


@router.post("/login", dependencies=[Depends(rate_limit.rate_limit_login)])
async def login(data: LoginRequestModel, conn=Depends(postgresql.get_db)):
    try:
        response = await auth_service.login(conn, data)

        if not response["status"]:
            return JSONResponse(status_code=400, content={"detail": response["message"]})

        token = response["data"]["access_token"]
        response["data"].pop("access_token", None)

        resp = JSONResponse(status_code=200, content={"message": response["message"], "data": response["data"]})

        resp.set_cookie(
            key="auth",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            max_age=259200,
        )

        return resp
    except Exception as e:
        logger.error(e)
        return JSONResponse(status_code=500, content={"detail": "An error occurred during login"})


@router.post("/google/login", dependencies=[Depends(rate_limit.rate_limit_google_login)])
async def google_login(data: LoginGoogleRequestModel, conn=Depends(postgresql.get_db)):
    try:
        response = await auth_service.google_login(conn, data)

        if not response["status"]:
            return JSONResponse(status_code=400, content={"detail": response["message"]})

        token = response["data"]["access_token"]
        response["data"].pop("access_token", None)

        resp = JSONResponse(status_code=200, content={"message": response["message"], "data": response["data"]})

        resp.set_cookie(
            key="auth",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            max_age=259200,
        )

        return resp
    except Exception as e:
        logger.error(e)
        return JSONResponse(status_code=500, content={"detail": "An error occurred during Google login"})


@router.post("/logout", dependencies=[Depends(security.validate_token_wrapper)])
async def logout():
    try:
        payload = JSONResponse(status_code=200, content={"message": "Successfully logged out"})
        payload.delete_cookie(
            key="auth",
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        return payload
    except Exception as e:
        logger.error(e)
        return JSONResponse(status_code=500, content={"detail": "An error occurred during logout"})


@router.post("/forget-password", dependencies=[Depends(rate_limit.rate_limit_forget_password)])
async def forget_password(

        data: ForgetPasswordRequestModel, conn=Depends(postgresql.get_db),
        clientmq=Depends(rabbitmq.get_channel), redis_client=Depends(redis_cache.get_redis)

):
    try:
        response = await auth_service.forget_password(conn, clientmq, redis_client, data)

        if not response["status"]:
            return JSONResponse(status_code=200, content={"detail": response["message"]})

        token = response["data"]["access_token"]
        response["data"].pop("access_token", None)

        resp = JSONResponse(status_code=200, content={"message": response["message"]})
        resp.set_cookie(
            key="auth_reset",
            value=token,
            httponly=True,
            samesite="lax",
            path="/",
            max_age=900,
            secure=True,
        )

        return resp
    except Exception as e:
        logger.error(e)
        return JSONResponse(status_code=500, content={"detail": "An error occurred during forget password"})


@router.post("/validate-code", dependencies=[Depends(rate_limit.rate_limit_validate_code)])
async def validate_code(
    data: ValidateCodeRequest,
    user=Depends(security.validate_token_to_validate_code),
    redis_client=Depends(redis_cache.get_redis)
):
    try:
        response = await auth_service.validate_code(redis_client, data.code, user)

        if not response["status"]:
            return JSONResponse(status_code=400, content={"detail": response["message"]})

        token = response["data"]["access_token"]
        response["data"].pop("access_token", None)

        resp = JSONResponse(status_code=200, content={"message": response["message"]})
        resp.set_cookie(
            key="auth_reset",
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            max_age=900,
        )

        return resp
    except Exception as e:
        logger.error(e)
        return JSONResponse(status_code=500, content={"detail": "An error occurred during code validation"})


@router.post("/update-password")
async def update_password(
    data: UpdatePasswordRequest,
    user=Depends(security.validate_token_to_update_password),
    conn=Depends(postgresql.get_db)
):
    try:
        user_id = security.get_user_id(user)
        response = await user_service.update_password(conn, user_id, data.password)

        if not response["status"]:
            return JSONResponse(status_code=400, content={"detail": response["message"]})

        resp = JSONResponse(status_code=200, content={"message": response["message"]})
        resp.delete_cookie(
            key="auth_reset",
            path="/",
            secure=True,
            httponly=True,
            samesite="lax",
        )

        return resp
    except Exception as e:
        logger.error(e)
        return JSONResponse(status_code=500, content={"detail": "An error occurred during password update"})
