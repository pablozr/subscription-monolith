from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from tests.unit.helpers import AsyncContextManager
from workers.schedule import renewal_reminder


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 3, 29, 9, 0, 0, tzinfo=tz)


class RenewalReminderTests(TestCase):
    def test_reagendar_tarefa_schedules_for_next_day_at_2210(self):
        scheduler = MagicMock()
        now = datetime(2026, 3, 29, 9, 30, 0)

        renewal_reminder.reagendar_tarefa(scheduler, None, now)

        scheduled_timestamp = scheduler.enterabs.call_args.args[0]
        scheduled_for = datetime.fromtimestamp(scheduled_timestamp)
        self.assertEqual(scheduled_for, datetime(2026, 3, 30, 22, 10, 0))


class RenewalReminderExecutionTests(IsolatedAsyncioTestCase):
    async def test_check_renewal_reminders_publishes_messages_and_disconnects(self):
        scheduler = MagicMock()
        conn = SimpleNamespace(fetch=AsyncMock(return_value=[{
            "id": 1,
            "name": "Netflix",
            "price": 39.9,
            "billing_cycle": "MONTHLY",
            "next_payment_date": date(2026, 3, 31),
            "email": "user@test.com",
            "fullname": "Test User",
        }]))
        pool = SimpleNamespace(acquire=lambda: AsyncContextManager(conn))

        with patch("workers.schedule.renewal_reminder.datetime", FixedDateTime), \
             patch("workers.schedule.renewal_reminder.postgresql.connect", AsyncMock()), \
             patch("workers.schedule.renewal_reminder.rabbitmq.connect", AsyncMock()), \
            patch("workers.schedule.renewal_reminder.postgresql.disconnect", AsyncMock()) as pg_disconnect, \
            patch("workers.schedule.renewal_reminder.rabbitmq.disconnect", AsyncMock()) as mq_disconnect, \
            patch("workers.schedule.renewal_reminder.messaging_service.publish_notification", AsyncMock()) as publish_notification, \
            patch.object(renewal_reminder.postgresql, "pool", pool), \
            patch.object(renewal_reminder.rabbitmq, "channel", object()), \
            patch("workers.schedule.renewal_reminder.reagendar_tarefa") as reagendar:
            await renewal_reminder.check_renewal_reminders(scheduler, timezone.utc)

        publish_notification.assert_awaited_once()
        pg_disconnect.assert_awaited_once()
        mq_disconnect.assert_awaited_once()
        reagendar.assert_called_once()
