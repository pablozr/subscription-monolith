import asyncio
import uuid
from datetime import date
from typing import cast
from unittest import IsolatedAsyncioTestCase

import asyncpg

from core.config.config import settings
from schemas.payment_history import PaymentHistoryCreateRequest
from services.payment_history import payment_history_service


class AsyncBarrier:
    def __init__(self, parties: int):
        self.parties = parties
        self.arrived = 0
        self.lock = asyncio.Lock()
        self.event = asyncio.Event()

    async def wait(self):
        async with self.lock:
            self.arrived += 1
            if self.arrived >= self.parties:
                self.event.set()

        await asyncio.wait_for(self.event.wait(), timeout=2)


class BarrierInsertConnection:
    def __init__(self, conn: asyncpg.Connection, barrier: AsyncBarrier):
        self.conn = conn
        self.barrier = barrier

    def transaction(self):
        return self.conn.transaction()

    async def fetchrow(self, query: str, *args):
        if "INSERT INTO payment_history" in " ".join(query.split()):
            await self.barrier.wait()

        return await self.conn.fetchrow(query, *args)


class FailingSubscriptionUpdateConnection:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    def transaction(self):
        return self.conn.transaction()

    async def fetchrow(self, query: str, *args):
        if "UPDATE subscriptions" in " ".join(query.split()):
            return None

        return await self.conn.fetchrow(query, *args)


class CancelBeforeInsertConnection:
    def __init__(
        self,
        conn: asyncpg.Connection,
        cancel_conn: asyncpg.Connection,
        subscription_id: int,
        user_id: int,
    ):
        self.conn = conn
        self.cancel_conn = cancel_conn
        self.subscription_id = subscription_id
        self.user_id = user_id
        self.cancelled = False

    def transaction(self):
        return self.conn.transaction()

    async def fetchrow(self, query: str, *args):
        normalized_query = " ".join(query.split())

        if not self.cancelled and "INSERT INTO payment_history" in normalized_query:
            self.cancelled = True
            await self.cancel_conn.execute(
                """
                UPDATE subscriptions
                SET status = 'CANCELED', updated_at = NOW()
                WHERE id = $1 AND user_id = $2
                """,
                self.subscription_id,
                self.user_id,
            )

        return await self.conn.fetchrow(query, *args)


class PaymentHistoryReliabilityIntegrationTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dsn = (
            f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}"
            f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        )

        try:
            self.admin_conn = await asyncpg.connect(dsn=self.dsn, timeout=2)
        except Exception as exc:
            self.skipTest(f"PostgreSQL is not accessible for payment history integration tests: {exc}")

        self.schema_name = f"test_payment_history_{uuid.uuid4().hex}"

        await self.admin_conn.execute(f'CREATE SCHEMA "{self.schema_name}"')
        await self.admin_conn.execute(f'SET search_path TO "{self.schema_name}"')
        await self.admin_conn.execute(
            """
            CREATE TABLE subscriptions (
                id BIGINT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                price NUMERIC(10, 2) NOT NULL,
                billing_cycle VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL,
                next_payment_date DATE,
                updated_at TIMESTAMP NULL
            )
            """
        )
        await self.admin_conn.execute(
            """
            CREATE TABLE payment_history (
                id BIGSERIAL PRIMARY KEY,
                subscription_id BIGINT NOT NULL REFERENCES subscriptions(id),
                user_id BIGINT NOT NULL,
                reference_date DATE NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                paid_at DATE NOT NULL,
                payment_method VARCHAR(50),
                reference VARCHAR(120),
                notes VARCHAR(500),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (subscription_id, reference_date)
            )
            """
        )

    async def asyncTearDown(self):
        if hasattr(self, "admin_conn") and not self.admin_conn.is_closed():
            if hasattr(self, "schema_name"):
                await self.admin_conn.execute(f'DROP SCHEMA IF EXISTS "{self.schema_name}" CASCADE')
            await self.admin_conn.close()

    async def _connect_in_schema(self) -> asyncpg.Connection:
        conn = await asyncpg.connect(dsn=self.dsn, timeout=2)
        await conn.execute(f'SET search_path TO "{self.schema_name}"')
        return conn

    async def _seed_subscription(
        self,
        subscription_id: int = 1,
        user_id: int = 10,
        price: float = 49.90,
        billing_cycle: str = "MONTHLY",
        status: str = "ACTIVE",
        next_payment_date: date | None = date(2026, 2, 5),
    ):
        await self.admin_conn.execute(
            """
            INSERT INTO subscriptions (id, user_id, price, billing_cycle, status, next_payment_date)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            subscription_id,
            user_id,
            price,
            billing_cycle,
            status,
            next_payment_date,
        )

    async def _seed_active_subscription(self):
        await self._seed_subscription()

    async def _insert_payment_history(
        self,
        subscription_id: int,
        user_id: int,
        reference_date: date,
        paid_at: date,
        amount: float = 49.90,
        payment_method: str = "pix",
        reference: str | None = None,
    ) -> int:
        row = await self.admin_conn.fetchrow(
            """
            INSERT INTO payment_history
                (subscription_id, user_id, reference_date, amount, paid_at, payment_method, reference, notes, created_at)
            VALUES
                ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            RETURNING id
            """,
            subscription_id,
            user_id,
            reference_date,
            amount,
            paid_at,
            payment_method,
            reference,
            "seeded",
        )

        return int(row["id"])

    async def test_create_payment_allows_only_one_insert_under_concurrency_for_same_reference_date(self):
        await self._seed_active_subscription()

        conn_one = await self._connect_in_schema()
        conn_two = await self._connect_in_schema()
        barrier = AsyncBarrier(2)

        try:
            request = PaymentHistoryCreateRequest(paymentMethod="pix", paidAt=date(2026, 2, 5), reference="ref-1")

            first_result, second_result = await asyncio.gather(
                payment_history_service.create_payment(
                    cast(asyncpg.Connection, BarrierInsertConnection(conn_one, barrier)),
                    1,
                    10,
                    request,
                ),
                payment_history_service.create_payment(
                    cast(asyncpg.Connection, BarrierInsertConnection(conn_two, barrier)),
                    1,
                    10,
                    request,
                ),
            )
        finally:
            await conn_one.close()
            await conn_two.close()

        self.assertCountEqual(
            [result["status"] for result in [first_result, second_result]],
            [True, False],
        )
        self.assertEqual(
            sorted(result["message"] for result in [first_result, second_result]),
            ["Payment already registered for this reference date", "Payment registered successfully"],
        )

        payment_count = await self.admin_conn.fetchval("SELECT COUNT(*) FROM payment_history WHERE subscription_id = $1", 1)
        next_payment_date = await self.admin_conn.fetchval(
            "SELECT next_payment_date FROM subscriptions WHERE id = $1 AND user_id = $2",
            1,
            10,
        )

        self.assertEqual(payment_count, 1)
        self.assertEqual(next_payment_date, date(2026, 3, 5))

    async def test_create_payment_rolls_back_insert_when_subscription_update_fails(self):
        await self._seed_active_subscription()
        conn = await self._connect_in_schema()

        try:
            result = await payment_history_service.create_payment(
                cast(asyncpg.Connection, FailingSubscriptionUpdateConnection(conn)),
                1,
                10,
                PaymentHistoryCreateRequest(paymentMethod="pix", paidAt=date(2026, 2, 5), reference="ref-atomic"),
            )
        finally:
            await conn.close()

        self.assertEqual(
            result,
            {"status": False, "message": "Failed to update subscription next payment date", "data": {}},
        )

        payment_count = await self.admin_conn.fetchval("SELECT COUNT(*) FROM payment_history WHERE subscription_id = $1", 1)
        next_payment_date = await self.admin_conn.fetchval(
            "SELECT next_payment_date FROM subscriptions WHERE id = $1 AND user_id = $2",
            1,
            10,
        )

        self.assertEqual(payment_count, 0, "Payment insert should be rolled back when subscription update fails")
        self.assertEqual(next_payment_date, date(2026, 2, 5))

    async def test_get_subscription_payment_history_applies_ordering_and_pagination(self):
        await self._seed_active_subscription()
        first_id = await self._insert_payment_history(1, 10, date(2026, 1, 1), date(2026, 1, 10))
        second_id = await self._insert_payment_history(1, 10, date(2026, 2, 1), date(2026, 3, 5))
        third_id = await self._insert_payment_history(1, 10, date(2026, 3, 1), date(2026, 3, 5))
        fourth_id = await self._insert_payment_history(1, 10, date(2026, 4, 1), date(2026, 2, 1))

        conn = await self._connect_in_schema()
        try:
            result = await payment_history_service.get_subscription_payment_history(conn, 1, 10, 2, 1)
            full_result = await payment_history_service.get_subscription_payment_history(conn, 1, 10, 10, 0)
        finally:
            await conn.close()

        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["pagination"], {"limit": 2, "offset": 1})
        self.assertEqual(
            [item["id"] for item in result["data"]["payments"]],
            [second_id, fourth_id],
        )
        self.assertEqual(
            [item["id"] for item in full_result["data"]["payments"]],
            [third_id, second_id, fourth_id, first_id],
        )

    async def test_get_user_payment_history_applies_filters_and_excludes_other_users(self):
        await self._seed_subscription(subscription_id=1, user_id=10, next_payment_date=date(2026, 1, 10))
        await self._seed_subscription(subscription_id=2, user_id=10, next_payment_date=date(2026, 1, 15))
        await self._seed_subscription(subscription_id=3, user_id=20, next_payment_date=date(2026, 1, 20))

        await self._insert_payment_history(1, 10, date(2026, 1, 1), date(2026, 1, 5), reference="u10-sub1-a")
        filtered_target_id = await self._insert_payment_history(1, 10, date(2026, 2, 1), date(2026, 2, 5), reference="u10-sub1-b")
        await self._insert_payment_history(2, 10, date(2026, 2, 20), date(2026, 2, 20), reference="u10-sub2-a")
        await self._insert_payment_history(3, 20, date(2026, 2, 10), date(2026, 2, 10), reference="u20-sub3-a")

        conn = await self._connect_in_schema()
        try:
            filtered_result = await payment_history_service.get_user_payment_history(
                conn,
                10,
                1,
                date(2026, 2, 1),
                date(2026, 2, 28),
                10,
                0,
            )
            full_result = await payment_history_service.get_user_payment_history(conn, 10, None, None, None, 10, 0)
            idor_result = await payment_history_service.get_subscription_payment_history(conn, 3, 10, 10, 0)
        finally:
            await conn.close()

        self.assertTrue(filtered_result["status"])
        self.assertEqual(len(filtered_result["data"]["payments"]), 1)
        self.assertEqual(filtered_result["data"]["payments"][0]["id"], filtered_target_id)
        self.assertEqual(filtered_result["data"]["payments"][0]["subscriptionId"], 1)
        self.assertEqual(filtered_result["data"]["payments"][0]["userId"], 10)

        self.assertTrue(full_result["status"])
        self.assertEqual(len(full_result["data"]["payments"]), 3)
        self.assertTrue(all(payment["userId"] == 10 for payment in full_result["data"]["payments"]))

        self.assertTrue(idor_result["status"])
        self.assertEqual(idor_result["data"]["payments"], [])

    async def test_create_payment_advances_next_payment_date_when_paid_early(self):
        await self._seed_subscription(
            subscription_id=1,
            user_id=10,
            billing_cycle="MONTHLY",
            status="ACTIVE",
            next_payment_date=date(2026, 6, 10),
        )
        conn = await self._connect_in_schema()

        try:
            result = await payment_history_service.create_payment(
                conn,
                1,
                10,
                PaymentHistoryCreateRequest(paymentMethod="pix", paidAt=date(2026, 5, 1), reference="early-ref"),
            )
        finally:
            await conn.close()

        stored_reference_date = await self.admin_conn.fetchval(
            "SELECT reference_date FROM payment_history WHERE subscription_id = $1",
            1,
        )
        next_payment_date = await self.admin_conn.fetchval(
            "SELECT next_payment_date FROM subscriptions WHERE id = $1 AND user_id = $2",
            1,
            10,
        )

        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["subscription"]["nextPaymentDate"], "2026-07-10")
        self.assertEqual(stored_reference_date, date(2026, 6, 10))
        self.assertEqual(next_payment_date, date(2026, 7, 10))

    async def test_create_payment_catches_up_multiple_cycles_when_paid_late(self):
        await self._seed_subscription(
            subscription_id=1,
            user_id=10,
            billing_cycle="MONTHLY",
            status="ACTIVE",
            next_payment_date=date(2026, 1, 10),
        )
        conn = await self._connect_in_schema()

        try:
            result = await payment_history_service.create_payment(
                conn,
                1,
                10,
                PaymentHistoryCreateRequest(paymentMethod="pix", paidAt=date(2026, 4, 15), reference="late-ref"),
            )
        finally:
            await conn.close()

        stored_reference_date = await self.admin_conn.fetchval(
            "SELECT reference_date FROM payment_history WHERE subscription_id = $1",
            1,
        )
        next_payment_date = await self.admin_conn.fetchval(
            "SELECT next_payment_date FROM subscriptions WHERE id = $1 AND user_id = $2",
            1,
            10,
        )

        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["subscription"]["nextPaymentDate"], "2026-05-10")
        self.assertEqual(stored_reference_date, date(2026, 1, 10))
        self.assertEqual(next_payment_date, date(2026, 5, 10))

    async def test_create_payment_uses_paid_at_as_reference_when_next_payment_date_is_null(self):
        await self._seed_subscription(
            subscription_id=1,
            user_id=10,
            billing_cycle="MONTHLY",
            status="ACTIVE",
            next_payment_date=None,
        )
        conn = await self._connect_in_schema()

        try:
            result = await payment_history_service.create_payment(
                conn,
                1,
                10,
                PaymentHistoryCreateRequest(paymentMethod="pix", paidAt=date(2026, 4, 15), reference="null-next"),
            )
        finally:
            await conn.close()

        stored_reference_date = await self.admin_conn.fetchval(
            "SELECT reference_date FROM payment_history WHERE subscription_id = $1",
            1,
        )
        next_payment_date = await self.admin_conn.fetchval(
            "SELECT next_payment_date FROM subscriptions WHERE id = $1 AND user_id = $2",
            1,
            10,
        )

        self.assertTrue(result["status"])
        self.assertEqual(result["data"]["subscription"]["nextPaymentDate"], "2026-05-15")
        self.assertEqual(stored_reference_date, date(2026, 4, 15))
        self.assertEqual(next_payment_date, date(2026, 5, 15))

    async def test_create_payment_does_not_insert_when_billing_cycle_is_invalid(self):
        await self._seed_subscription(
            subscription_id=1,
            user_id=10,
            billing_cycle="DAILY",
            status="ACTIVE",
            next_payment_date=date(2026, 2, 5),
        )
        conn = await self._connect_in_schema()

        try:
            result = await payment_history_service.create_payment(
                conn,
                1,
                10,
                PaymentHistoryCreateRequest(paymentMethod="pix", paidAt=date(2026, 2, 5), reference="invalid-cycle"),
            )
        finally:
            await conn.close()

        payment_count = await self.admin_conn.fetchval(
            "SELECT COUNT(*) FROM payment_history WHERE subscription_id = $1",
            1,
        )
        next_payment_date = await self.admin_conn.fetchval(
            "SELECT next_payment_date FROM subscriptions WHERE id = $1 AND user_id = $2",
            1,
            10,
        )

        self.assertEqual(
            result,
            {"status": False, "message": "Invalid billing cycle for subscription", "data": {}},
        )
        self.assertEqual(payment_count, 0)
        self.assertEqual(next_payment_date, date(2026, 2, 5))

    async def test_create_payment_should_not_register_payment_if_subscription_is_canceled_concurrently(self):
        await self._seed_active_subscription()
        create_conn = await self._connect_in_schema()
        cancel_conn = await self._connect_in_schema()

        try:
            result = await payment_history_service.create_payment(
                cast(asyncpg.Connection, CancelBeforeInsertConnection(create_conn, cancel_conn, 1, 10)),
                1,
                10,
                PaymentHistoryCreateRequest(paymentMethod="pix", paidAt=date(2026, 2, 5), reference="cancel-race"),
            )
        finally:
            await create_conn.close()
            await cancel_conn.close()

        payment_count = await self.admin_conn.fetchval(
            "SELECT COUNT(*) FROM payment_history WHERE subscription_id = $1",
            1,
        )
        subscription_status = await self.admin_conn.fetchval(
            "SELECT status FROM subscriptions WHERE id = $1 AND user_id = $2",
            1,
            10,
        )

        self.assertFalse(
            result["status"],
            "Payment creation should fail when subscription is canceled concurrently",
        )
        self.assertEqual(subscription_status, "CANCELED")
        self.assertEqual(payment_count, 0)
