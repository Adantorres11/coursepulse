from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Profile
from classrooms.models import Classroom, Enrollment
from quizzes.models import (
    Attempt,
    Answer,
    Lecture,
    Question,
    QuizCompletion,
)


class LectureUnpublishTests(APITestCase):
    def setUp(self):
        self.professor = self.create_user(
            "professor", "professor"
        )
        self.other_professor = self.create_user(
            "other_professor", "professor"
        )
        self.student = self.create_user(
            "student", "student"
        )

        self.classroom = Classroom.objects.create(
            name="Software Engineering",
            professor=self.professor,
        )

        Enrollment.objects.create(
            user=self.student,
            classroom=self.classroom,
        )

        self.lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Lecture 1",
            published_at=timezone.now(),
        )

        self.question = Question.objects.create(
            lecture=self.lecture,
            prompt="What is 2 + 2?",
            choices=["4", "3", "5", "6"],
            correct_index=0,
            difficulty="easy",
        )

        self.url = reverse(
            "lecture-unpublish",
            args=[self.lecture.id],
        )

    def create_user(self, username, role):
        user = User.objects.create_user(
            username=username,
            password="testpass",
        )
        Profile.objects.create(user=user, role=role)
        return user

    def test_professor_can_unpublish(self):
        self.client.force_authenticate(
            user=self.professor
        )

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["id"], self.lecture.id
        )
        self.assertIsNone(response.data["published_at"])

        self.lecture.refresh_from_db()
        self.assertIsNone(self.lecture.published_at)

    def test_unpublish_preserves_existing_records(self):
        attempt = Attempt.objects.create(
            user=self.student,
            lecture=self.lecture,
            total_points=100,
            completed_at=timezone.now(),
        )

        answer = Answer.objects.create(
            attempt=attempt,
            question=self.question,
            chosen_index=0,
            is_correct=True,
            time_taken_ms=1000,
            points_awarded=100,
        )

        completion = QuizCompletion.objects.create(
            user=self.student,
            lecture=self.lecture,
        )

        self.client.force_authenticate(
            user=self.professor
        )
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)

        attempt.refresh_from_db()
        answer.refresh_from_db()
        completion.refresh_from_db()
        self.question.refresh_from_db()

        self.assertEqual(attempt.total_points, 100)
        self.assertIsNotNone(attempt.completed_at)
        self.assertTrue(answer.is_correct)
        self.assertEqual(answer.points_awarded, 100)

    def test_unpublished_quiz_hidden_from_students(self):
        quiz_url = reverse(
            "lecture-quiz",
            args=[self.lecture.id],
        )

        self.client.force_authenticate(
            user=self.student
        )

        response = self.client.get(quiz_url)
        self.assertEqual(response.status_code, 200)

        self.client.force_authenticate(
            user=self.professor
        )
        self.client.post(self.url)

        self.client.force_authenticate(
            user=self.student
        )

        response = self.client.get(quiz_url)
        self.assertEqual(response.status_code, 404)

        response = self.client.get(
            reverse("lecture-list")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_already_unpublished_quiz(self):
        self.lecture.published_at = None
        self.lecture.save(update_fields=["published_at"])

        self.client.force_authenticate(
            user=self.professor
        )
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["published_at"])

    def test_other_professor_cannot_unpublish(self):
        self.client.force_authenticate(
            user=self.other_professor
        )
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)

        self.lecture.refresh_from_db()
        self.assertIsNotNone(self.lecture.published_at)

    def test_student_cannot_unpublish(self):
        self.client.force_authenticate(
            user=self.student
        )
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unknown_lecture(self):
        self.client.force_authenticate(
            user=self.professor
        )

        response = self.client.post(
            reverse(
                "lecture-unpublish",
                args=[self.lecture.id + 10000],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 401)