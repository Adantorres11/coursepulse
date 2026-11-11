from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from classrooms.models import Classroom
from .grading import QUESTION_TIME_LIMIT_MS
from .models import Answer, Attempt, Lecture, QuizCompletion
from .test_lectures import add_questions


class AnswerEndpointTests(APITestCase):
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
        cls.user = get_user_model().objects.create_user(
            username="student", password="pw"
        )

    def setUp(self):
        self.client.force_authenticate(self.user)

    def url(self, lecture_id=None):
        return f"/api/lectures/{lecture_id or self.lecture.id}/answers/"

    def post(self, chosen_index, time_taken_ms=4200, question_id=None, url=None):
        return self.client.post(
            url or self.url(),
            {
                "question_id": question_id or self.question.id,
                "chosen_index": chosen_index,
                "time_taken_ms": time_taken_ms,
            },
            format="json",
        )

    def test_correct_answer_is_graded_and_saved(self):
        response = self.post(self.question.correct_index)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "is_correct": True,
                "points_awarded": 100,
                "total_points": 100,
                "correct_index": self.question.correct_index,
            },
        )
        answer = Answer.objects.get()
        self.assertEqual(answer.question, self.question)
        self.assertEqual(answer.chosen_index, self.question.correct_index)
        self.assertTrue(answer.is_correct)
        self.assertEqual(answer.time_taken_ms, 4200)
        self.assertEqual(answer.points_awarded, 100)
        attempt = Attempt.objects.get()
        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.lecture, self.lecture)
        self.assertEqual(attempt.total_points, 100)
        self.assertEqual(answer.attempt, attempt)

    def test_wrong_answer_earns_zero_and_still_returns_correct_index(self):
        response = self.post(self.question.correct_index + 1)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertFalse(body["is_correct"])
        self.assertEqual(body["points_awarded"], 0)
        self.assertEqual(body["total_points"], 0)
        self.assertEqual(body["correct_index"], self.question.correct_index)

    def test_timeout_answer_earns_zero(self):
        response = self.post(
            self.question.correct_index, QUESTION_TIME_LIMIT_MS + 1
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["is_correct"])
        self.assertEqual(response.json()["points_awarded"], 0)
        self.assertEqual(Answer.objects.get().points_awarded, 0)

    def test_logged_out_request_is_401(self):
        self.client.force_authenticate(None)
        response = self.post(self.question.correct_index)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Answer.objects.count(), 0)
        self.assertEqual(Attempt.objects.count(), 0)

    def test_unknown_lecture_is_404(self):
        response = self.post(0, url=self.url(lecture_id=999999))
        self.assertEqual(response.status_code, 404)

    def test_unpublished_lecture_is_404(self):
        future = Lecture.objects.create(
            classroom=self.classroom,
            title="Future",
            published_at=timezone.now() + timedelta(days=1),
        )
        add_questions(future, 1)
        question = future.questions.get()
        response = self.post(
            0, question_id=question.id, url=self.url(lecture_id=future.id)
        )
        self.assertEqual(response.status_code, 404)

    def test_unknown_question_is_404(self):
        response = self.post(0, question_id=999999)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Answer.objects.count(), 0)

    def test_question_from_another_lecture_is_404(self):
        other = Lecture.objects.create(
            classroom=self.classroom,
            title="Other",
            published_at=timezone.now() - timedelta(hours=1),
        )
        add_questions(other, 1)
        response = self.post(0, question_id=other.questions.get().id)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Answer.objects.count(), 0)

    def test_invalid_body_is_rejected_and_not_saved(self):
        bad_bodies = [
            ("chosen_index", {"question_id": self.question.id, "chosen_index": 4, "time_taken_ms": 100}),
            ("chosen_index", {"question_id": self.question.id, "chosen_index": -1, "time_taken_ms": 100}),
            ("time_taken_ms", {"question_id": self.question.id, "chosen_index": 0}),
            ("time_taken_ms", {"question_id": self.question.id, "chosen_index": 0, "time_taken_ms": -5}),
        ]
        for field, body in bad_bodies:
            with self.subTest(body=body):
                response = self.client.post(self.url(), body, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertEqual(Answer.objects.count(), 0)

    def answer_all_correctly(self):
        for question in self.lecture.questions.order_by("position"):
            response = self.post(question.correct_index, question_id=question.id)
            self.assertEqual(response.status_code, 201)

    def test_repeat_answer_is_400_and_total_unchanged(self):
        self.post(self.question.correct_index)
        response = self.post(self.question.correct_index + 1)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "This question was already answered in this attempt."},
        )
        self.assertEqual(Answer.objects.count(), 1)
        self.assertEqual(Attempt.objects.get().total_points, 100)

    def test_total_points_is_the_running_total(self):
        second = self.lecture.questions.order_by("position").last()
        second.difficulty = "medium"
        second.save()
        self.post(self.question.correct_index)
        response = self.post(second.correct_index, question_id=second.id)
        self.assertEqual(response.json()["total_points"], 300)

    def test_last_answer_completes_the_attempt(self):
        self.answer_all_correctly()
        self.assertIsNotNone(Attempt.objects.get().completed_at)
        self.assertEqual(
            QuizCompletion.objects.filter(
                user=self.user, lecture=self.lecture
            ).count(),
            1,
        )

    def test_replay_after_completion_starts_new_attempt(self):
        self.answer_all_correctly()
        response = self.post(self.question.correct_index)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Attempt.objects.count(), 2)
        self.assertEqual(response.json()["total_points"], 100)
        self.assertEqual(QuizCompletion.objects.count(), 1)

    def test_answers_from_two_students_stay_separate(self):
        other = get_user_model().objects.create_user(
            username="other", password="pw"
        )
        self.post(self.question.correct_index)
        self.client.force_authenticate(other)
        response = self.post(self.question.correct_index + 1)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["total_points"], 0)
        self.assertEqual(Attempt.objects.count(), 2)
        self.assertEqual(Attempt.objects.get(user=self.user).total_points, 100)
