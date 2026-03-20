from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse
from core.logger.logger import logger
from schemas.auth import LoginRequestModel, LoginGoogleRequestModel
from services.auth import auth_service
from core.postgresql.postgresql import postgresql

router = APIRouter()


@router.post("/login")
async def login(data: LoginRequestModel, conn=Depends(postgresql.get_db)):
    try:
        response = await auth_service.login(conn, data)

        if not response["status"]:
            return JSONResponse(status_code=400, content={"detail": response["message"]})

        token = response["data"]["token"]
        response["data"].pop("token", None)

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

        token = response["data"]["token"]
        response["data"].pop("token", None)

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
