import asyncio

from core.logger.logger import logger
from core.config.config import settings
from core.postgresql.postgresql import postgresql
from core.rabbitmq.rabbitmq import rabbitmq
from services.messaging import messaging_service


async def check_renewal_reminders():
    await postgresql.connect()
    await rabbitmq.connect()

    query = """
            SELECT s.id, s.name, s.price, s.billing_cycle, s.next_payment_date,
                   u.email, u.fullname
            FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE s.status = 'ACTIVE'
              AND s.next_payment_date - s.reminder_days_before * INTERVAL '1 day' <= CURRENT_DATE
              AND s.next_payment_date >= CURRENT_DATE
            """

    try:
        async with postgresql.pool.acquire() as conn:
            rows = await conn.fetch(query)

        logger.info(f"Found {len(rows)} subscriptions due for reminder")

        for row in rows:
            payload = {
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

            await messaging_service.publish("email-queue", payload, rabbitmq.channel)
            logger.info(f"Reminder queued for {row['email']} - {row['name']}")

    except Exception as e:
        logger.exception(e)
    finally:
        await postgresql.disconnect()
        await rabbitmq.disconnect()


if __name__ == "__main__":
    asyncio.run(check_renewal_reminders())
