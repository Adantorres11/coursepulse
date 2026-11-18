from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .models import Lecture


class SeedDemoStatusTests(TestCase):
    def test_seeded_lecture_is_ready(self):
        call_command("seed_demo", stdout=StringIO())

        lecture = Lecture.objects.get(title="Demo Lecture: Scrum and Git")
        self.assertEqual(lecture.status, "ready")
        self.assertIsNotNone(lecture.published_at)

    def test_reseeding_fixes_a_pending_demo_lecture(self):
        call_command("seed_demo", stdout=StringIO())
        Lecture.objects.update(status="pending")

        call_command("seed_demo", stdout=StringIO())

        self.assertEqual(
            Lecture.objects.get(title="Demo Lecture: Scrum and Git").status,
            "ready",
        )
