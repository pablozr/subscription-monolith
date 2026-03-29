from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from core.postgresql.postgresql import postgresql
from core.security import security
from functions.utils.utils import default_response
from schemas.payment_history import PaymentHistoryCreateRequest
from services.payment_history import payment_history_service


router = APIRouter()


@router.post("/subscriptions/{subscription_id}")
async def create_payment(
    subscription_id: int,
    data: PaymentHistoryCreateRequest | None = None,
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    user_id = security.get_user_id(user)
    return await default_response(
        payment_history_service.create_payment,
        [conn, subscription_id, user_id, data],
        is_creation=True
    )


@router.post("/{payment_id}/void")
async def void_payment(
    payment_id: int = Path(gt=0),
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    user_id = security.get_user_id(user)
    return await default_response(
        payment_history_service.void_payment,
        [conn, payment_id, user_id]
    )


@router.get("/subscriptions/{subscription_id}")
async def get_subscription_payment_history(
    subscription_id: int,
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    user_id = security.get_user_id(user)
    return await default_response(
        payment_history_service.get_subscription_payment_history,
        [conn, subscription_id, user_id, limit, offset]
    )


@router.get("/history")
async def get_user_payment_history(
    subscription_id: int | None = Query(default=None, alias="subscriptionId", gt=0),
    start_date: date | None = Query(default=None, alias="startDate"),
    end_date: date | None = Query(default=None, alias="endDate"),
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="startDate cannot be greater than endDate")

    user_id = security.get_user_id(user)

    return await default_response(
        payment_history_service.get_user_payment_history,
        [conn, user_id, subscription_id, start_date, end_date, limit, offset]
    )
