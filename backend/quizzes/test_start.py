from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from classrooms.models import Classroom
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
