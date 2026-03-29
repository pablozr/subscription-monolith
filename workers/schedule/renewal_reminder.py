import asyncio
import sched
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.logger.logger import logger
from core.config.config import settings
from core.postgresql.postgresql import postgresql
from core.rabbitmq.rabbitmq import rabbitmq
from services.messaging import messaging_service


async def check_renewal_reminders(scheduler, brazil_tz):
    actual_datetime = datetime.now(tz=brazil_tz)
    actual_date = actual_datetime.date()

    try:
        await postgresql.connect()
        await rabbitmq.connect()

        if not postgresql.pool:
            raise RuntimeError("PostgreSQL pool is not initialized")

        if not rabbitmq.channel:
            raise RuntimeError("RabbitMQ channel is not initialized")

        pool = postgresql.pool
        channel = rabbitmq.channel

        query = """
            SELECT s.id, s.name, s.price, s.billing_cycle, s.next_payment_date,
                   u.email, u.fullname
            FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE s.status = 'ACTIVE'
              AND (s.next_payment_date - (s.reminder_days_before * INTERVAL '1 day'))::date = $1::date
              AND s.next_payment_date >= $1::date
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, actual_date)

        logger.info(f"Found {len(rows)} subscriptions due for reminder on {actual_date}")

        for row in rows:
            payload = {
                "event": "renewal-reminder",
                "email": {
                    "to": row["email"],
                    "from": settings.EMAIL_FROM,
                    "html": f"""
                        <h2>Lembrete de Renovação</h2>
                        <p>Olá {row['fullname']},</p>
                        <p>Sua assinatura <strong>{row['name']}</strong> no valor de
                        <strong>R$ {row['price']:.2f}</strong> ({row['billing_cycle']})
                        será renovada em <strong>{row['next_payment_date']}</strong>.</p>
                    """,
                    "subject": f"Lembrete: {row['name']} será renovada em breve",
                    "base64Attachment": "",
                    "base64AttachmentName": "",
                    "message": ""
                }
            }

            await messaging_service.publish_notification(payload, channel)
            logger.info(f"Reminder queued for {row['email']} - {row['name']}")

    except Exception as e:
        logger.exception(f"Error while checking renewal reminders: {e}")

    finally:
        try:
            reagendar_tarefa(scheduler, brazil_tz, actual_datetime)
        except Exception as e:
            logger.exception(f"Error while rescheduling task: {e}")

        try:
            await postgresql.disconnect()
        except Exception as e:
            logger.exception(f"Error disconnecting PostgreSQL: {e}")

        try:
            await rabbitmq.disconnect()
        except Exception as e:
            logger.exception(f"Error disconnecting RabbitMQ: {e}")


def reagendar_tarefa(scheduler, brazil_tz, actual_datetime):
    try:
        next_run_on_function = actual_datetime.replace(
            hour=22,
            minute=10,
            second=0,
            microsecond=0
        ) + timedelta(days=1)

        print("-" * 60)
        print(f"Tarefa reagendada para: {next_run_on_function}")
        print("-" * 60)

        scheduler.enterabs(
            next_run_on_function.timestamp(),
            1,
            lambda: run_scheduler(scheduler, brazil_tz)
        )

    except Exception as e:
        logger.exception(f"Error while scheduling next execution: {e}")


def run_scheduler(scheduler, brazil_tz):
    try:
        asyncio.run(check_renewal_reminders(scheduler, brazil_tz))
    except Exception as e:
        logger.exception(f"Error running scheduler task: {e}")


if __name__ == "__main__":
    brazil_tz = ZoneInfo("America/Sao_Paulo")
    scheduler = sched.scheduler(time.time, time.sleep)

    now = datetime.now(tz=brazil_tz)
    first_run = now.replace(hour=22, minute=10, second=0, microsecond=0)

    if now >= first_run:
        first_run += timedelta(days=1)

    print("-" * 60)
    print(f"Primeira execução agendada para: {first_run}")
    print("-" * 60)

    scheduler.enterabs(
        first_run.timestamp(),
        1,
        lambda: run_scheduler(scheduler, brazil_tz)
    )

    scheduler.run()
