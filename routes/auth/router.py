from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse
from core.logger.logger import logger
from schemas.auth import LoginRequestModel, LoginGoogleRequestModel, ForgetPasswordRequestModel
from services.auth import auth_service
from core.postgresql.postgresql import postgresql
from core.security import security
from core.rabbitmq.rabbitmq import rabbitmq
from core.redis.redis import redis_cache

router = APIRouter()


@router.post("/login")
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


@router.post("/google/login")
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


@router.post("/logout", dependencies= [Depends(security.validate_token_wrapper)])
async def logout():
    try:
        payload = JSONResponse(status_code=200, content={"message": "Successfully logged out"})
        payload.delete_cookie("auth")
        return payload
    except Exception as e:
        logger.error(e)
        return JSONResponse(status_code=500, content={"detail": "An error occurred during logout"})


@router.post("/forget-password")
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
