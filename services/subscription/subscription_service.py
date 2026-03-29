from datetime import date
from dateutil.relativedelta import relativedelta
import asyncpg
from asyncpg.exceptions import UniqueViolationError, ForeignKeyViolationError

from schemas.subscription import SubscriptionCreateRequest, SubscriptionUpdateRequest
from core.logger.logger import logger
from functions.utils.utils import update_default_dict


CYCLE_OFFSETS = {
    "WEEKLY": relativedelta(weeks=1),
    "MONTHLY": relativedelta(months=1),
    "YEARLY": relativedelta(years=1),
}


def calculate_next_payment(start_date: date, billing_cycle: str) -> date:
    return start_date + CYCLE_OFFSETS[billing_cycle]


async def get_all_subscriptions(conn: asyncpg.Connection, user_id: int) -> dict:
    query = """
            SELECT id, user_id, name, price, billing_cycle, status,
                   start_date, next_payment_date, reminder_days_before, canceled_at
            FROM subscriptions
            WHERE user_id = $1
            ORDER BY next_payment_date ASC
            """

    try:
        rows = await conn.fetch(query, user_id)
        subscriptions = [
            update_default_dict(
                {**row},
                decimal_targets=["price"],
                date_targets=["start_date", "next_payment_date", "canceled_at"]
            ) for row in rows
        ]

        return {
            "status": True,
            "message": "Subscriptions retrieved successfully",
            "data": {"subscriptions": subscriptions}
        }
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while fetching subscriptions", "data": {}}


async def get_one_subscription(conn: asyncpg.Connection, subscription_id: int, user_id: int) -> dict:
    query = """
            SELECT id, user_id, name, price, billing_cycle, status,
                   start_date, next_payment_date, reminder_days_before, canceled_at
            FROM subscriptions
            WHERE id = $1 AND user_id = $2
            """

    try:
        row = await conn.fetchrow(query, subscription_id, user_id)

        if not row:
            return {"status": False, "message": "Subscription not found", "data": {}}

        subscription = update_default_dict(
            {**row},
            decimal_targets=["price"],
            date_targets=["start_date", "next_payment_date"]
        )

        return {
            "status": True,
            "message": "Subscription retrieved successfully",
            "data": {"subscription": subscription}
        }
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while fetching subscription", "data": {}}


async def create_subscription(conn: asyncpg.Connection, user_id: int, data: SubscriptionCreateRequest) -> dict:
    insert_query = """
                   INSERT INTO subscriptions (user_id, name, price, billing_cycle, status, start_date, next_payment_date, reminder_days_before)
                   VALUES ($1, $2, $3, $4, 'ACTIVE', $5, $6, $7)
                   RETURNING id, user_id, name, price, billing_cycle, status, start_date, next_payment_date, reminder_days_before
                   """

    try:
        next_payment = calculate_next_payment(data.start_date, data.billing_cycle)

        async with conn.transaction():
            row = await conn.fetchrow(
                insert_query,
                user_id,
                data.name,
                data.price,
                data.billing_cycle,
                data.start_date,
                next_payment,
                data.reminder_days_before
            )

            if not row:
                return {"status": False, "message": "Failed to create subscription", "data": {}}

            subscription = update_default_dict(
                {**row},
                decimal_targets=["price"],
                date_targets=["start_date", "next_payment_date"]
            )

            return {
                "status": True,
                "message": "Subscription created successfully",
                "data": {"subscription": subscription}
            }
    except ForeignKeyViolationError:
        return {"status": False, "message": "Invalid user", "data": {}}
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while creating subscription", "data": {}}


async def update_subscription(conn: asyncpg.Connection, subscription_id: int, user_id: int, data: SubscriptionUpdateRequest) -> dict:
    allowed_columns = {"name", "price", "billing_cycle", "status", "next_payment_date", "reminder_days_before"}
    filtered = {k: v for k, v in data.model_dump(exclude_none=True).items() if k in allowed_columns}

    if not filtered:
        return {"status": False, "message": "No fields to update", "data": {}}

    columns = list(filtered.keys())
    values = list(filtered.values())

    set_clause = ", ".join(f"{col} = ${i}" for i, col in enumerate(columns, 1))
    cancel_clause = ", canceled_at = NOW()" if filtered.get("status") == "CANCELED" else ""
    idx = len(values) + 1
    values.append(subscription_id)
    values.append(user_id)

    update_query = f"""
        UPDATE subscriptions SET {set_clause}{cancel_clause}, updated_at = NOW()
        WHERE id = ${idx} AND user_id = ${idx + 1}
        RETURNING id, user_id, name, price, billing_cycle, status, start_date, next_payment_date, reminder_days_before, canceled_at
    """

    try:
        async with conn.transaction():
            row = await conn.fetchrow(update_query, *values)

            if not row:
                return {"status": False, "message": "Subscription not found", "data": {}}

            subscription = update_default_dict(
                {**row},
                decimal_targets=["price"],
                date_targets=["start_date", "next_payment_date", "canceled_at"]
            )

            return {
                "status": True,
                "message": "Subscription updated successfully",
                "data": {"subscription": subscription}
            }
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while updating subscription", "data": {}}


async def cancel_subscription(conn: asyncpg.Connection, subscription_id: int, user_id: int) -> dict:
    update_query = """
                   UPDATE subscriptions SET status = 'CANCELED', canceled_at = NOW(), updated_at = NOW()
                   WHERE id = $1 AND user_id = $2 AND status = 'ACTIVE'
                   RETURNING id
                   """

    try:
        async with conn.transaction():
            row = await conn.fetchrow(update_query, subscription_id, user_id)

            if not row:
                return {"status": False, "message": "Subscription not found or already canceled", "data": {}}

            return {
                "status": True,
                "message": "Subscription canceled successfully",
                "data": {"id": row["id"]}
            }
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while canceling subscription", "data": {}}


async def delete_subscription(conn: asyncpg.Connection, subscription_id: int, user_id: int) -> dict:
    delete_query = """
                   DELETE FROM subscriptions
                   WHERE id = $1 AND user_id = $2
                   RETURNING id
                   """

    try:
        async with conn.transaction():
            row = await conn.fetchrow(delete_query, subscription_id, user_id)

            if not row:
                return {"status": False, "message": "Subscription not found", "data": {}}

            return {
                "status": True,
                "message": "Subscription deleted successfully",
                "data": {"id": row["id"]}
            }
    except Exception as e:
        logger.error(e)
        return {"status": False, "message": "An error occurred while deleting subscription", "data": {}}
