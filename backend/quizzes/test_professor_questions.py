
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import Profile
from classrooms.models import Classroom, Enrollment
from quizzes.models import Answer, Attempt, Lecture, Question


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


class QuestionReviewGapTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.professor = self._user("owner", "professor")
        self.student = self._user("student", "student")
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
            title="Draft lecture",
            status="ready",
        )
        self.question = self._question("What is Python?", position=1)
        self._auth(self.professor)

    def _user(self, username, role):
        user = User.objects.create_user(username=username, password="testpass")
        Profile.objects.create(user=user, role=role)
        return user

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _question(self, prompt, position, choices=None):
        return Question.objects.create(
            lecture=self.lecture,
            prompt=prompt,
            choices=choices or ["Language", "Database", "Browser", "OS"],
            correct_index=0,
            difficulty="easy",
            position=position,
        )

    def _questions_url(self):
        return reverse("professor-lecture-questions", args=[self.lecture.id])

    def _detail_url(self, question):
        return reverse(
            "professor-question-detail",
            args=[self.lecture.id, question.id],
        )

    def _publish(self):
        return self.client.post(
            reverse("lecture-publish", args=[self.lecture.id])
        )

    def _payload(self, **overrides):
        payload = {
            "prompt": "What is Django?",
            "choices": ["Framework", "OS", "Browser", "Database"],
            "correct_index": 0,
            "difficulty": "easy",
        }
        payload.update(overrides)
        return payload

    def test_publish_rejects_lecture_that_is_not_ready(self):
        for lecture_status in ("pending", "processing", "failed"):
            with self.subTest(status=lecture_status):
                self.lecture.status = lecture_status
                self.lecture.published_at = None
                self.lecture.save(update_fields=["status", "published_at"])

                response = self._publish()

                self.assertEqual(response.status_code, 400)
                self.lecture.refresh_from_db()
                self.assertIsNone(self.lecture.published_at)

    def test_publish_allows_a_ready_lecture(self):
        response = self._publish()

        self.assertEqual(response.status_code, 200)
        self.lecture.refresh_from_db()
        self.assertIsNotNone(self.lecture.published_at)

    def test_publish_rejects_blank_or_duplicate_choices(self):
        cases = (
            ["Yes", "No", "   ", "Maybe"],
            ["Yes", " yes ", "No", "Maybe"],
            ["Same", "same", "Other", "Else"],
        )
        for choices in cases:
            with self.subTest(choices=choices):
                self.question.choices = choices
                self.question.save()
                self.lecture.published_at = None
                self.lecture.status = "ready"
                self.lecture.save(update_fields=["published_at", "status"])

                response = self._publish()

                self.assertEqual(response.status_code, 400)
                self.lecture.refresh_from_db()
                self.assertIsNone(self.lecture.published_at)

    def test_create_rejects_blank_and_duplicate_choices(self):
        cases = (
            ["A", "B", " ", "D"],
            ["A", "B", "C"],
            ["A", "B", "C", "D", "E"],
            ["Apple", "APPLE", "Pear", "Plum"],
            ["  Yes  ", "yes", "No", "Maybe"],
        )
        for choices in cases:
            with self.subTest(choices=choices):
                response = self.client.post(
                    self._questions_url(),
                    self._payload(choices=choices),
                    format="json",
                )
                self.assertEqual(response.status_code, 400)

        self.assertEqual(self.lecture.questions.count(), 1)

    def test_create_stores_trimmed_choices(self):
        response = self.client.post(
            self._questions_url(),
            self._payload(choices=["  Framework  ", " OS ", "Browser", "Database"]),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["choices"],
            ["Framework", "OS", "Browser", "Database"],
        )

    def test_new_question_is_appended_and_ignores_client_position(self):
        self._question("Second", position=2)

        response = self.client.post(
            self._questions_url(),
            self._payload(position=99),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["position"], 3)
        created = Question.objects.get(pk=response.data["id"])
        self.assertEqual(created.position, 3)

    def test_delete_keeps_positions_contiguous(self):
        second = self._question("Second", position=5)
        third = self._question("Third", position=9)

        response = self.client.delete(self._detail_url(second))

        self.assertEqual(response.status_code, 204)
        self.question.refresh_from_db()
        third.refresh_from_db()
        self.assertEqual(self.question.position, 1)
        self.assertEqual(third.position, 2)

    def test_delete_with_student_answers_keeps_scores(self):
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
        self.lecture.published_at = timezone.now()
        self.lecture.save(update_fields=["published_at"])
        self.client.post(reverse("lecture-unpublish", args=[self.lecture.id]))

        response = self.client.delete(self._detail_url(self.question))

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Question.objects.filter(pk=self.question.id).exists())
        answer.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(answer.points_awarded, 100)
        self.assertEqual(attempt.total_points, 100)
        self.assertIsNotNone(attempt.completed_at)

    def test_replace_with_student_answers_keeps_scores(self):
        attempt = Attempt.objects.create(
            user=self.student,
            lecture=self.lecture,
            total_points=200,
            completed_at=timezone.now(),
        )
        Answer.objects.create(
            attempt=attempt,
            question=self.question,
            chosen_index=0,
            is_correct=True,
            time_taken_ms=800,
            points_awarded=200,
        )

        response = self.client.patch(
            self._detail_url(self.question),
            {
                "prompt": "A different question",
                "choices": ["One", "Two", "Three", "Four"],
                "correct_index": 3,
                "difficulty": "hard",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.question.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(self.question.prompt, "What is Python?")
        self.assertEqual(self.question.correct_index, 0)
        self.assertEqual(attempt.total_points, 200)

    def test_student_cannot_review_edit_or_publish(self):
        self._auth(self.student)
        calls = (
            ("get", self._questions_url(), None),
            ("post", self._questions_url(), self._payload()),
            ("patch", self._detail_url(self.question), {"prompt": "Nope"}),
            ("delete", self._detail_url(self.question), None),
            ("post", reverse("lecture-publish", args=[self.lecture.id]), None),
        )
        for method, url, body in calls:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, body, format="json")
                self.assertEqual(response.status_code, 403)
                self.assertNotIn(b"What is Python?", response.content)

        self.lecture.refresh_from_db()
        self.assertIsNone(self.lecture.published_at)
        self.assertTrue(Question.objects.filter(pk=self.question.id).exists())

    def test_student_cannot_see_unpublished_questions(self):
        self._auth(self.student)
        quiz = self.client.get(reverse("lecture-quiz", args=[self.lecture.id]))
        listing = self.client.get(reverse("lecture-list"))

        self.assertEqual(quiz.status_code, 404)
        self.assertNotIn(b"What is Python?", quiz.content)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data, [])
