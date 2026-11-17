
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import Profile
from classrooms.models import Classroom
from quizzes.models import Lecture, Question


class ProfessorQuestionTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.professor = User.objects.create_user(
            username="professor",
            password="testpass",
        )
        Profile.objects.create(
            user=self.professor,
            role="professor",
        )

        self.other_professor = User.objects.create_user(
            username="other_professor",
            password="testpass",
        )
        Profile.objects.create(
            user=self.other_professor,
            role="professor",
        )

        self.classroom = Classroom.objects.create(
            name="Software Engineering",
            professor=self.professor,
        )

        self.lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Introduction",
            status="ready",
        )

        self.question = Question.objects.create(
            lecture=self.lecture,
            prompt="What is Python?",
            choices=[
                "Language",
                "Database",
                "Browser",
                "OS",
            ],
            correct_index=0,
            difficulty="easy",
            position=1,
        )

        self.questions_url = reverse(
            "professor-lecture-questions",
            args=[self.lecture.id],
        )
        self.detail_url = reverse(
            "professor-question-detail",
            args=[self.lecture.id, self.question.id],
        )
        self.publish_url = reverse(
            "lecture-publish",
            args=[self.lecture.id],
        )

        token, _ = Token.objects.get_or_create(
            user=self.professor
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

    def test_get_questions(self):
        response = self.client.get(self.questions_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["correct_index"], 0)

    def test_create_question(self):
        response = self.client.post(
            self.questions_url,
            {
                "prompt": "What is Django?",
                "choices": ["Framework", "OS", "Browser", "DB"],
                "correct_index": 0,
                "difficulty": "easy",
                "position": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Question.objects.filter(lecture=self.lecture).count(),
            2,
        )

    def test_edit_question(self):
        response = self.client.patch(
            self.detail_url,
            {"prompt": "Updated question"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual(self.question.prompt, "Updated question")

    def test_delete_question(self):
        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Question.objects.filter(pk=self.question.id).exists()
        )

    def test_publish_quiz(self):
        response = self.client.post(self.publish_url)

        self.assertEqual(response.status_code, 200)
        self.lecture.refresh_from_db()
        self.assertIsNotNone(self.lecture.published_at)

    def test_other_professor_forbidden(self):
        token, _ = Token.objects.get_or_create(
            user=self.other_professor
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

        response = self.client.get(self.questions_url)

        self.assertEqual(response.status_code, 403)

    def test_publish_empty_quiz_rejected(self):
        Question.objects.all().delete()

        response = self.client.post(self.publish_url)

        self.assertEqual(response.status_code, 400)

    def test_cannot_edit_published_quiz(self):
        self.client.post(self.publish_url)

        response = self.client.patch(
            self.detail_url,
            {"prompt": "Changed after publishing"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)


    def test_invalid_choices_rejected(self):
        response = self.client.post(
            self.questions_url,
            {
                "prompt": "Invalid question",
                "choices": ["A", "B"],
                "correct_index": 0,
                "difficulty": "easy",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_correct_index_rejected(self):
        response = self.client.post(
            self.questions_url,
            {
                "prompt": "Invalid answer",
                "choices": ["A", "B", "C", "D"],
                "correct_index": 5,
                "difficulty": "easy",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_lecture_returns_404(self):
        response = self.client.get(
            reverse("professor-lecture-questions", args=[999999])
        )
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user_rejected(self):
        self.client.credentials()

        response = self.client.get(self.questions_url)

        self.assertIn(response.status_code, [401, 403])

    def test_other_professor_cannot_publish(self):
        token, _ = Token.objects.get_or_create(
            user=self.other_professor
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

        response = self.client.post(self.publish_url)

        self.assertEqual(response.status_code, 403)
