from django.conf import settings
from django.test import SimpleTestCase

from config.celery import app
from core.tasks import ping


class PingTaskTests(SimpleTestCase):
    def test_ping_returns_pong(self):
        # apply() runs the task inline, so this needs no Redis and no worker.
        self.assertEqual(ping.apply().get(), "pong")

    def test_ping_logs_a_line(self):
        with self.assertLogs("core.tasks", level="INFO") as logs:
            ping.apply()
        self.assertIn("ping task ran", logs.output[0])

    def test_ping_is_registered(self):
        self.assertIn("core.tasks.ping", app.tasks)


class CeleryConfigTests(SimpleTestCase):
    def test_app_reads_celery_settings_from_django(self):
        self.assertEqual(app.conf.broker_url, settings.CELERY_BROKER_URL)
        self.assertEqual(app.conf.result_backend, settings.CELERY_RESULT_BACKEND)
        self.assertEqual(app.conf.task_serializer, "json")
        self.assertEqual(app.conf.result_serializer, "json")
        self.assertEqual(list(app.conf.accept_content), ["json"])
        self.assertTrue(app.conf.task_acks_late)
        self.assertEqual(app.conf.worker_prefetch_multiplier, 1)
        self.assertEqual(app.conf.task_time_limit, settings.CELERY_TASK_TIME_LIMIT)
        self.assertEqual(app.conf.task_soft_time_limit, settings.CELERY_TASK_SOFT_TIME_LIMIT)
        self.assertLess(settings.CELERY_TASK_SOFT_TIME_LIMIT, settings.CELERY_TASK_TIME_LIMIT)
        self.assertEqual(app.conf.timezone, settings.TIME_ZONE)
