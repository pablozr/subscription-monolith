from fastapi import APIRouter, Depends
from core.postgresql.postgresql import postgresql
from core.security import security
from schemas.user import UserCreateRequest, UserUpdateRequest
from services.user import user_service
from functions.utils.utils import default_response

router = APIRouter()


@router.get("/me")
async def get_me(
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    return await default_response(
        user_service.get_one_user,
        [conn, user["id"]]
    )


@router.put("/me")
async def update_me(
    data: UserUpdateRequest,
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    return await default_response(
        user_service.update_user_auto,
        [conn, user["id"], data]
    )


@router.post("")
async def create_user(
    data: UserCreateRequest,
    conn=Depends(postgresql.get_db)
):
    return await default_response(
        user_service.create_user,
        [conn, data],
        is_creation=True
    )
