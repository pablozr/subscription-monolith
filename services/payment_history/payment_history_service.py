from datetime import date

import asyncpg
from asyncpg.exceptions import UniqueViolationError
from dateutil.relativedelta import relativedelta

from core.logger.logger import logger
from functions.utils.utils import update_default_dict
from schemas.payment_history import PaymentHistoryCreateRequest


CYCLE_OFFSETS = {
    "WEEKLY": relativedelta(weeks=1),
    "MONTHLY": relativedelta(months=1),
    "YEARLY": relativedelta(years=1),
}


def calculate_next_payment_date(current_next_payment: date, paid_at: date, billing_cycle: str) -> date:
    next_payment = current_next_payment
    cycle_offset = CYCLE_OFFSETS[billing_cycle]

    if next_payment > paid_at:
        return next_payment + cycle_offset

    while next_payment <= paid_at:
        next_payment += cycle_offset

    return next_payment


def parse_payment_history_rows(rows: list[asyncpg.Record]) -> list[dict]:
    parsed_rows = [
        update_default_dict(
            {**row},
            decimal_targets=["amount"],
            date_targets=["paid_at", "created_at"]
        )
        for row in rows
    ]

    return [
        {
            "id": row["id"],
            "subscriptionId": row["subscription_id"],
            "userId": row["user_id"],
            "amount": row["amount"],
            "paidAt": row["paid_at"],
            "paymentMethod": row["payment_method"],
            "reference": row["reference"],
            "notes": row["notes"],
            "createdAt": row["created_at"],
        }
        for row in parsed_rows
    ]


async def create_payment(
    conn: asyncpg.Connection,
    subscription_id: int,
    user_id: int,
    data: PaymentHistoryCreateRequest
) -> dict:
    select_subscription_query = """
        SELECT id, user_id, price, billing_cycle, status, next_payment_date
        FROM subscriptions
        WHERE id = $1 AND user_id = $2
    """

    insert_payment_query = """
        INSERT INTO payment_history
            (subscription_id, user_id, reference_date, amount, paid_at, payment_method, reference, notes, created_at)
        VALUES
            ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        RETURNING id, subscription_id, user_id, amount, paid_at, payment_method, reference, notes, created_at
    """

    update_subscription_query = """
        UPDATE subscriptions
        SET next_payment_date = $1,
            updated_at = NOW()
        WHERE id = $2 AND user_id = $3 AND status = 'ACTIVE' AND billing_cycle = $4
        RETURNING id, next_payment_date
    """

    try:
        async with conn.transaction():
            subscription = await conn.fetchrow(select_subscription_query, subscription_id, user_id)

            if not subscription:
                raise ValueError("Subscription not found")

            if subscription["status"] != "ACTIVE":
                raise ValueError("Subscription not active")

            if subscription["billing_cycle"] not in CYCLE_OFFSETS:
                raise ValueError("Invalid billing cycle")

            paid_at = data.paid_at or date.today()
            amount = data.amount if data.amount is not None else float(subscription["price"])
            reference_date = subscription["next_payment_date"] or paid_at

            payment = await conn.fetchrow(
                insert_payment_query,
                subscription_id,
                user_id,
                reference_date,
                amount,
                paid_at,
                data.payment_method,
                data.reference,
                data.notes
            )

            if not payment:
                raise ValueError("Payment not registered for this reference date")

            next_payment_date = calculate_next_payment_date(
                current_next_payment=reference_date,
                paid_at=paid_at,
                billing_cycle=subscription["billing_cycle"]
            )

            updated_subscription = await conn.fetchrow(
                update_subscription_query,
                next_payment_date,
                subscription_id,
                user_id,
                subscription["billing_cycle"]
            )

            if not updated_subscription:
                raise ValueError("Failed to update subscription next payment date")

            parsed_payment = update_default_dict(
                {**payment},
                decimal_targets=["amount"],
                date_targets=["paid_at", "created_at"]
            )

            payment_data = {
                "id": parsed_payment["id"],
                "subscriptionId": parsed_payment["subscription_id"],
                "userId": parsed_payment["user_id"],
                "amount": parsed_payment["amount"],
                "paidAt": parsed_payment["paid_at"],
                "paymentMethod": parsed_payment["payment_method"],
                "reference": parsed_payment["reference"],
                "notes": parsed_payment["notes"],
                "createdAt": parsed_payment["created_at"],
            }

            return {
                "status": True,
                "message": "Payment registered successfully",
                "data": {
                    "payment": payment_data,
                    "subscription": {
                        "id": updated_subscription["id"],
                        "subscriptionId": updated_subscription["id"],
                        "nextPaymentDate": str(updated_subscription["next_payment_date"])
                    }
                }
            }
    except UniqueViolationError:
        return {"status": False, "message": "Payment already registered for this reference date", "data": {}}
    except ValueError as e:
        return {"status": False, "message": str(e), "data": {}}
    except Exception as e:
        logger.exception(e)
        return {"status": False, "message": "An error occurred while registering payment", "data": {}}


async def get_subscription_payment_history(
    conn: asyncpg.Connection,
    subscription_id: int,
    user_id: int,
    limit: int,
    offset: int,
) -> dict:
    query = """
        SELECT id, subscription_id, user_id, amount, paid_at, payment_method, reference, notes, created_at
        FROM payment_history
        WHERE subscription_id = $1
          AND user_id = $2
        ORDER BY paid_at DESC, id DESC
        LIMIT $3 OFFSET $4
    """

    try:
        rows = await conn.fetch(query, subscription_id, user_id, limit, offset)
        payments = parse_payment_history_rows(list(rows))

        return {
            "status": True,
            "message": "Payment history retrieved successfully",
            "data": {
                "payments": payments,
                "pagination": {
                    "limit": limit,
                    "offset": offset
                }
            }
        }
    except Exception as e:
        logger.exception(e)
        return {"status": False, "message": "An error occurred while fetching payment history", "data": {}}


async def get_user_payment_history(
    conn: asyncpg.Connection,
    user_id: int,
    subscription_id: int | None,
    start_date: date | None,
    end_date: date | None,
    limit: int,
    offset: int,
) -> dict:
    where_clauses = ["user_id = $1"]
    query_params: list[object] = [user_id]
    placeholder_index = 2

    if subscription_id is not None:
        where_clauses.append(f"subscription_id = ${placeholder_index}")
        query_params.append(subscription_id)
        placeholder_index += 1

    if start_date is not None:
        where_clauses.append(f"paid_at >= ${placeholder_index}")
        query_params.append(start_date)
        placeholder_index += 1

    if end_date is not None:
        where_clauses.append(f"paid_at <= ${placeholder_index}")
        query_params.append(end_date)
        placeholder_index += 1

    limit_placeholder = f"${placeholder_index}"
    query_params.append(limit)
    placeholder_index += 1

    offset_placeholder = f"${placeholder_index}"
    query_params.append(offset)

    query = f"""
        SELECT id, subscription_id, user_id, amount, paid_at, payment_method, reference, notes, created_at
        FROM payment_history
        WHERE {' AND '.join(where_clauses)}
        ORDER BY paid_at DESC, id DESC
        LIMIT {limit_placeholder} OFFSET {offset_placeholder}
    """

    try:
        rows = await conn.fetch(query, *query_params)
        payments = parse_payment_history_rows(list(rows))

        return {
            "status": True,
            "message": "Payment history retrieved successfully",
            "data": {
                "payments": payments,
                "pagination": {
                    "limit": limit,
                    "offset": offset
                }
            }
        }
    except Exception as e:
        logger.exception(e)
        return {"status": False, "message": "An error occurred while fetching payment history", "data": {}}
