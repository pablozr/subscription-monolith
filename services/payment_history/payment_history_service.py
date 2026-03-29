from datetime import date

import asyncpg
from dateutil.relativedelta import relativedelta

from core.logger.logger import logger
from functions.utils.utils import update_default_dict
from schemas.payment_history import PaymentHistoryCreateRequest


CYCLE_OFFSETS = {
    "WEEKLY": relativedelta(weeks=1),
    "MONTHLY": relativedelta(months=1),
    "YEARLY": relativedelta(years=1),
}

PAYMENT_STATUS_PAID = "PAID"
PAYMENT_STATUS_VOIDED = "VOIDED"


def calculate_next_payment_date(current_next_payment: date, paid_at: date, billing_cycle: str) -> date:
    next_payment = current_next_payment
    cycle_offset = CYCLE_OFFSETS[billing_cycle]

    if next_payment > paid_at:
        return next_payment + cycle_offset

    while next_payment <= paid_at:
        next_payment += cycle_offset

    return next_payment


def parse_subscription_payload(subscription_id: int, next_payment_date: date | None) -> dict:
    return {
        "id": subscription_id,
        "subscriptionId": subscription_id,
        "nextPaymentDate": str(next_payment_date) if next_payment_date else None,
    }


def parse_payment_history_row(row: asyncpg.Record | dict) -> dict:
    parsed_row = update_default_dict(
        {**row},
        decimal_targets=["amount"],
        date_targets=["paid_at", "period_reference", "voided_at", "created_at"],
    )

    return {
        "id": parsed_row["id"],
        "subscriptionId": parsed_row["subscription_id"],
        "userId": parsed_row["user_id"],
        "amount": parsed_row["amount"],
        "paidAt": parsed_row["paid_at"],
        "periodReference": parsed_row["period_reference"],
        "status": parsed_row["status"] or PAYMENT_STATUS_PAID,
        "paymentMethod": parsed_row["payment_method"],
        "notes": parsed_row["notes"],
        "voidedAt": parsed_row["voided_at"],
        "createdAt": parsed_row["created_at"],
    }


def parse_payment_history_rows(rows: list[asyncpg.Record]) -> list[dict]:
    return [parse_payment_history_row(row) for row in rows]


async def create_payment(
    conn: asyncpg.Connection,
    subscription_id: int,
    user_id: int,
    data: PaymentHistoryCreateRequest | None = None
) -> dict:
    select_subscription_query = """
        SELECT id, user_id, price, billing_cycle, status, next_payment_date
        FROM subscriptions
        WHERE id = $1 AND user_id = $2
        FOR UPDATE
    """

    select_existing_payment_query = """
        SELECT id, subscription_id, user_id, amount, paid_at, period_reference,
               payment_method, notes, status, voided_at, created_at
        FROM payment_history
        WHERE subscription_id = $1
          AND user_id = $2
          AND paid_at = $3
          AND COALESCE(status, 'PAID') = $4
        ORDER BY id DESC
        LIMIT 1
    """

    insert_payment_query = """
        INSERT INTO payment_history
            (subscription_id, user_id, amount, paid_at, period_reference,
             payment_method, notes, status, created_at)
        VALUES
            ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        RETURNING id, subscription_id, user_id, amount, paid_at, period_reference,
                  payment_method, notes, status, voided_at, created_at
    """

    update_subscription_query = """
        UPDATE subscriptions
        SET next_payment_date = $1,
            updated_at = NOW()
        WHERE id = $2 AND user_id = $3
        RETURNING id, next_payment_date
    """

    try:
        async with conn.transaction():
            subscription = await conn.fetchrow(select_subscription_query, subscription_id, user_id)

            if not subscription:
                return {"status": False, "message": "Subscription not found", "data": {}}

            if subscription["status"] != "ACTIVE":
                return {"status": False, "message": "Cannot register payment for inactive subscription", "data": {}}

            if subscription["billing_cycle"] not in CYCLE_OFFSETS:
                return {"status": False, "message": "Invalid billing cycle for subscription", "data": {}}

            paid_at = data.paid_at if data and data.paid_at else date.today()
            amount = float(subscription["price"])
            current_next_payment = subscription["next_payment_date"] or paid_at

            existing_payment = await conn.fetchrow(
                select_existing_payment_query,
                subscription_id,
                user_id,
                paid_at,
                PAYMENT_STATUS_PAID,
            )

            if existing_payment:
                return {
                    "status": True,
                    "message": "Payment already registered for this date",
                    "data": {
                        "payment": parse_payment_history_row(existing_payment),
                        "subscription": parse_subscription_payload(
                            subscription["id"],
                            subscription["next_payment_date"],
                        ),
                        "alreadyPaid": True,
                    },
                }

            payment = await conn.fetchrow(
                insert_payment_query,
                subscription_id,
                user_id,
                amount,
                paid_at,
                current_next_payment,
                data.payment_method if data else None,
                data.notes if data else None,
                PAYMENT_STATUS_PAID,
            )

            if not payment:
                return {"status": False, "message": "Failed to register payment", "data": {}}

            next_payment_date = calculate_next_payment_date(
                current_next_payment=current_next_payment,
                paid_at=paid_at,
                billing_cycle=subscription["billing_cycle"]
            )

            updated_subscription = await conn.fetchrow(update_subscription_query, next_payment_date, subscription_id, user_id)

            if not updated_subscription:
                return {"status": False, "message": "Failed to update subscription next payment date", "data": {}}

            return {
                "status": True,
                "message": "Payment registered successfully",
                "data": {
                    "payment": parse_payment_history_row(payment),
                    "subscription": parse_subscription_payload(
                        updated_subscription["id"],
                        updated_subscription["next_payment_date"],
                    ),
                    "alreadyPaid": False,
                },
            }
    except Exception as e:
        logger.exception(e)
        return {"status": False, "message": "An error occurred while registering payment", "data": {}}


async def void_payment(
    conn: asyncpg.Connection,
    payment_id: int,
    user_id: int,
) -> dict:
    select_payment_query = """
        SELECT id, subscription_id, user_id, amount, paid_at,
               COALESCE(period_reference, paid_at) AS period_reference,
               payment_method, notes,
               COALESCE(status, 'PAID') AS status,
               voided_at, created_at
        FROM payment_history
        WHERE id = $1
          AND user_id = $2
        FOR UPDATE
    """

    select_subscription_query = """
        SELECT id, user_id
        FROM subscriptions
        WHERE id = $1
          AND user_id = $2
        FOR UPDATE
    """

    select_latest_active_payment_query = """
        SELECT id
        FROM payment_history
        WHERE subscription_id = $1
          AND user_id = $2
          AND COALESCE(status, 'PAID') = $3
        ORDER BY COALESCE(period_reference, paid_at) DESC, paid_at DESC, id DESC
        LIMIT 1
    """

    update_payment_query = """
        UPDATE payment_history
        SET status = $1,
            voided_at = NOW()
        WHERE id = $2
          AND user_id = $3
        RETURNING id, subscription_id, user_id, amount, paid_at,
                  COALESCE(period_reference, paid_at) AS period_reference,
                  payment_method, notes,
                  COALESCE(status, 'PAID') AS status,
                  voided_at, created_at
    """

    update_subscription_query = """
        UPDATE subscriptions
        SET next_payment_date = $1,
            updated_at = NOW()
        WHERE id = $2
          AND user_id = $3
        RETURNING id, next_payment_date
    """

    try:
        async with conn.transaction():
            payment = await conn.fetchrow(select_payment_query, payment_id, user_id)

            if not payment:
                return {"status": False, "message": "Payment not found", "data": {}}

            if payment["status"] == PAYMENT_STATUS_VOIDED:
                return {"status": False, "message": "Payment is already voided", "data": {}}

            subscription = await conn.fetchrow(select_subscription_query, payment["subscription_id"], user_id)

            if not subscription:
                return {"status": False, "message": "Subscription not found", "data": {}}

            latest_active_payment = await conn.fetchrow(
                select_latest_active_payment_query,
                payment["subscription_id"],
                user_id,
                PAYMENT_STATUS_PAID,
            )

            if not latest_active_payment or latest_active_payment["id"] != payment_id:
                return {
                    "status": False,
                    "message": "Only the latest active payment can be voided",
                    "data": {},
                }

            voided_payment = await conn.fetchrow(
                update_payment_query,
                PAYMENT_STATUS_VOIDED,
                payment_id,
                user_id,
            )

            if not voided_payment:
                return {"status": False, "message": "Failed to void payment", "data": {}}

            updated_subscription = await conn.fetchrow(
                update_subscription_query,
                payment["period_reference"],
                payment["subscription_id"],
                user_id,
            )

            if not updated_subscription:
                return {
                    "status": False,
                    "message": "Failed to rollback subscription next payment date",
                    "data": {},
                }

            return {
                "status": True,
                "message": "Payment voided successfully",
                "data": {
                    "payment": parse_payment_history_row(voided_payment),
                    "subscription": parse_subscription_payload(
                        updated_subscription["id"],
                        updated_subscription["next_payment_date"],
                    ),
                },
            }
    except Exception as e:
        logger.exception(e)
        return {"status": False, "message": "An error occurred while voiding payment", "data": {}}


async def get_subscription_payment_history(
    conn: asyncpg.Connection,
    subscription_id: int,
    user_id: int,
    limit: int,
    offset: int,
) -> dict:
    query = """
        SELECT id, subscription_id, user_id, amount, paid_at,
               COALESCE(period_reference, paid_at) AS period_reference,
               payment_method, notes,
               COALESCE(status, 'PAID') AS status,
               voided_at, created_at
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
    query = """
        SELECT id, subscription_id, user_id, amount, paid_at,
               COALESCE(period_reference, paid_at) AS period_reference,
               payment_method, notes,
               COALESCE(status, 'PAID') AS status,
               voided_at, created_at
        FROM payment_history
        WHERE user_id = $1
          AND ($2::BIGINT IS NULL OR subscription_id = $2::BIGINT)
          AND ($3::DATE IS NULL OR paid_at >= $3::DATE)
          AND ($4::DATE IS NULL OR paid_at <= $4::DATE)
        ORDER BY paid_at DESC, id DESC
        LIMIT $5 OFFSET $6
    """

    try:
        rows = await conn.fetch(query, user_id, subscription_id, start_date, end_date, limit, offset)
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
