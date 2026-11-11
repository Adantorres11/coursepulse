from datetime import timedelta
from importlib import import_module

from django.test import TestCase
from django.utils import timezone

from classrooms.models import Classroom
from .models import Answer, Attempt, Lecture
from .test_lectures import add_questions
from .testing import make_student


class MigrationBackfillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")
        cls.user = make_student("student", cls.classroom)

    def make_lecture(self, questions=1):
        lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Lecture",
            published_at=timezone.now() - timedelta(hours=1),
        )
        add_questions(lecture, questions)
        return lecture

    def test_answered_at_backfill_uses_attempt_start_time(self):
        lecture = self.make_lecture()
        attempt = Attempt.objects.create(user=self.user, lecture=lecture)
        answer = Answer.objects.create(
            attempt=attempt,
            question=lecture.questions.get(),
            chosen_index=0,
            is_correct=True,
            time_taken_ms=1000,
            answered_at=timezone.now() + timedelta(days=3),
        )
        migration = import_module("quizzes.migrations.0009_answer_answered_at")

        migration.copy_attempt_start_times(Answer, Attempt)

        answer.refresh_from_db()
        self.assertEqual(answer.answered_at, attempt.started_at)

    def test_duplicate_cleanup_keeps_valid_open_attempts(self):
        first, second = self.make_lecture(), self.make_lecture()
        done = Attempt.objects.create(
            user=self.user, lecture=first, completed_at=timezone.now()
        )
        open_one = Attempt.objects.create(user=self.user, lecture=first)
        open_two = Attempt.objects.create(user=self.user, lecture=second)
        migration = import_module(
            "quizzes.migrations.0007_attempt_unique_open_attempt"
        )

        migration.delete_duplicate_open_attempts(Attempt)

        self.assertEqual(
            set(Attempt.objects.values_list("id", flat=True)),
            {done.id, open_one.id, open_two.id},
        )
