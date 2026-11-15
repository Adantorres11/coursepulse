from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from classrooms.models import Classroom
from .grading import get_open_attempt, start_question
from .models import Attempt, Lecture, QuestionStart
from .test_lectures import add_questions
from .testing import answer, make_student, start


class QuestionStartTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")
        cls.lecture = Lecture.objects.create(
            classroom=cls.classroom,
            title="Lecture",
            published_at=timezone.now() - timedelta(hours=1),
        )
        add_questions(cls.lecture, 2)
        cls.question = cls.lecture.questions.order_by("position").first()
        cls.user = make_student("student", cls.classroom)

    def setUp(self):
        self.client.force_authenticate(self.user)

    def test_first_start_returns_201_and_creates_attempt(self):
        response = start(self.client, self.lecture, self.question)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["question_id"], self.question.id)
        self.assertIn("started_at", response.json())
        self.assertEqual(Attempt.objects.count(), 1)
        self.assertEqual(QuestionStart.objects.count(), 1)

    def test_second_start_keeps_original_time(self):
        start(self.client, self.lecture, self.question)
        backdated = timezone.now() - timedelta(seconds=10)
        QuestionStart.objects.update(started_at=backdated)
        response = start(self.client, self.lecture, self.question)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuestionStart.objects.count(), 1)
        self.assertEqual(QuestionStart.objects.get().started_at, backdated)

    def test_start_after_answer_returns_400(self):
        answer(self.client, self.lecture, self.question, 0)
        response = start(self.client, self.lecture, self.question)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "This question was already answered in this attempt."},
        )

    def test_professor_gets_403(self):
        self.client.force_authenticate(
            make_student("prof", self.classroom, role="professor")
        )
        response = start(self.client, self.lecture, self.question)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(), {"detail": "Only students can answer questions."}
        )
        self.assertFalse(Attempt.objects.exists())

    def test_not_enrolled_gets_403(self):
        self.client.force_authenticate(make_student("outsider"))
        response = start(self.client, self.lecture, self.question)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(), {"detail": "You must be enrolled in this class."}
        )
        self.assertFalse(Attempt.objects.exists())

    def test_question_from_other_lecture_is_404(self):
        other = Lecture.objects.create(
            classroom=self.classroom,
            title="Other",
            published_at=timezone.now() - timedelta(hours=1),
        )
        add_questions(other, 1)
        response = start(self.client, self.lecture, other.questions.get())
        self.assertEqual(response.status_code, 404)
        self.assertFalse(QuestionStart.objects.exists())

    def test_no_token_is_401(self):
        self.client.force_authenticate(None)
        response = start(self.client, self.lecture, self.question)
        self.assertEqual(response.status_code, 401)


class OpenAttemptTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")
        cls.lecture = Lecture.objects.create(
            classroom=cls.classroom,
            title="Lecture",
            published_at=timezone.now() - timedelta(hours=1),
        )
        add_questions(cls.lecture, 1)
        cls.question = cls.lecture.questions.get()
        cls.user = make_student("student", cls.classroom)

    def test_second_open_attempt_is_rejected(self):
        Attempt.objects.create(user=self.user, lecture=self.lecture)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attempt.objects.create(user=self.user, lecture=self.lecture)

    def test_completed_attempt_and_open_attempt_are_allowed(self):
        Attempt.objects.create(
            user=self.user, lecture=self.lecture, completed_at=timezone.now()
        )
        Attempt.objects.create(user=self.user, lecture=self.lecture)
        self.assertEqual(Attempt.objects.count(), 2)

    def test_start_reuses_the_existing_open_attempt(self):
        attempt = Attempt.objects.create(user=self.user, lecture=self.lecture)
        record, created = start_question(self.user, self.lecture, self.question)
        self.assertTrue(created)
        self.assertEqual(record.attempt, attempt)
        self.assertEqual(Attempt.objects.count(), 1)

    def test_start_recovers_when_another_request_created_the_attempt(self):
        attempt = Attempt.objects.create(user=self.user, lecture=self.lecture)
        real = get_open_attempt
        calls = []

        def first_call_misses(*args, **kwargs):
            calls.append(1)
            return None if len(calls) == 1 else real(*args, **kwargs)

        with patch("quizzes.grading.get_open_attempt", first_call_misses):
            record, created = start_question(
                self.user, self.lecture, self.question
            )
        self.assertTrue(created)
        self.assertEqual(record.attempt, attempt)
        self.assertEqual(Attempt.objects.count(), 1)
