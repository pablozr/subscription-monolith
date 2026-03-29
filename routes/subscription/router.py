from fastapi import APIRouter, Depends
from core.postgresql.postgresql import postgresql
from core.security import security
from schemas.subscription import SubscriptionCreateRequest, SubscriptionUpdateRequest
from services.subscription import subscription_service
from functions.utils.utils import default_response

router = APIRouter()


@router.get("")
async def get_all_subscriptions(
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    user_id = security.get_user_id(user)
    return await default_response(
        subscription_service.get_all_subscriptions,
        [conn, user_id]
    )


@router.get("/{subscription_id}")
async def get_one_subscription(
    subscription_id: int,
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    user_id = security.get_user_id(user)
    return await default_response(
        subscription_service.get_one_subscription,
        [conn, subscription_id, user_id]
    )


@router.post("")
async def create_subscription(
    data: SubscriptionCreateRequest,
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    user_id = security.get_user_id(user)
    return await default_response(
        subscription_service.create_subscription,
        [conn, user_id, data],
        is_creation=True
    )


@router.put("/{subscription_id}")
async def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdateRequest,
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    user_id = security.get_user_id(user)
    return await default_response(
        subscription_service.update_subscription,
        [conn, subscription_id, user_id, data]
    )


@router.patch("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: int,
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    user_id = security.get_user_id(user)
    return await default_response(
        subscription_service.cancel_subscription,
        [conn, subscription_id, user_id]
    )


@router.delete("/{subscription_id}")
async def delete_subscription(
    subscription_id: int,
    user=Depends(security.validate_token_wrapper),
    conn=Depends(postgresql.get_db)
):
    user_id = security.get_user_id(user)
    return await default_response(
        subscription_service.delete_subscription,
        [conn, subscription_id, user_id]
    )
