from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse
from core.logger.logger import logger
from core.postgresql.postgresql import postgresql
from schemas.user import UserCreateRequest
from services.user import user_service
from core.security import security

router = APIRouter()


@router.post("", dependencies=[Depends(security.validate_token_wrapper)])
async def create_user(data: UserCreateRequest, conn=Depends(postgresql.get_db)):
    try:
        response = await user_service.create_user(conn, data)

        if not response["status"]:
            return JSONResponse(status_code=400, content={"detail": "An error occurred. Please try again"})

        return JSONResponse(status_code=200, content={"message": "User created successfully"})
    except Exception as e:
        logger.error(e)
        return JSONResponse(status_code=500, content={"detail": "An error occurred. Please try again"})
