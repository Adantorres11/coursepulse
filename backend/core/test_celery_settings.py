from django.conf import settings
from django.test import SimpleTestCase


class CelerySettingsTests(SimpleTestCase):
    def test_worker_safety_settings(self):
        self.assertTrue(settings.CELERY_TASK_ACKS_LATE)
        self.assertEqual(settings.CELERY_WORKER_PREFETCH_MULTIPLIER, 1)
        self.assertTrue(settings.CELERY_TASK_REJECT_ON_WORKER_LOST)
        self.assertEqual(settings.CELERY_BROKER_TRANSPORT_OPTIONS["visibility_timeout"], 7200)
        self.assertEqual(settings.CELERY_BROKER_TRANSPORT_OPTIONS["socket_connect_timeout"], 3)
        self.assertEqual(settings.CELERY_BROKER_CONNECTION_TIMEOUT, 3)
        self.assertEqual(settings.CELERY_TASK_PUBLISH_RETRY_POLICY["max_retries"], 1)
        self.assertEqual(settings.CELERY_WORKER_MAX_TASKS_PER_CHILD, 10)
        self.assertEqual(settings.CELERY_WORKER_MAX_MEMORY_PER_CHILD, 500000)
        self.assertEqual(settings.CELERY_RESULT_EXPIRES, 86400)
        self.assertTrue(settings.CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP)
        self.assertGreater(
            settings.CELERY_BROKER_TRANSPORT_OPTIONS["visibility_timeout"],
            settings.CELERY_TASK_TIME_LIMIT + 300,
        )

    def test_tests_never_see_a_real_openai_key(self):
        self.assertEqual(settings.OPENAI_API_KEY, "")
