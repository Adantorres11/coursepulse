from unittest.mock import patch
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import Profile
from classrooms.models import Classroom
from quizzes.models import Lecture


class LectureStatusTests(TestCase):

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
            username="other",
            password="testpass",
        )
        Profile.objects.create(
            user=self.other_professor,
            role="professor",
        )

        self.student = User.objects.create_user(
            username="student",
            password="testpass",
        )
        Profile.objects.create(
            user=self.student,
            role="student",
        )

        self.classroom = Classroom.objects.create(
            name="Software Engineering",
            professor=self.professor,
        )

        self.lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Introduction",
            status="pending",
        )

        self.url = reverse(
            "lecture-status",
            args=[self.lecture.id],
        )
        self.retry_url = reverse(
            "lecture-retry",
            args=[self.lecture.id],
        )

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

    def test_pending_status(self):
        self.authenticate(self.professor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.lecture.id)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["error_message"], "")

    def test_processing_status(self):
        self.authenticate(self.professor)

        self.lecture.status = "processing"
        self.lecture.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "processing")
        self.assertEqual(response.data["error_message"], "")

    def test_ready_status(self):
        self.authenticate(self.professor)

        self.lecture.status = "ready"
        self.lecture.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ready")
        self.assertEqual(response.data["error_message"], "")

    def test_failed_status(self):
        self.authenticate(self.professor)

        self.lecture.status = "failed"
        self.lecture.error_message = "Transcription failed."
        self.lecture.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "failed")
        self.assertEqual(
            response.data["error_message"],
            "Transcription failed.",
        )

    def test_student_cannot_access_status(self):
        self.authenticate(self.student)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_other_professor_cannot_access_status(self):
        self.authenticate(self.other_professor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unknown_lecture(self):
        self.authenticate(self.professor)

        url = reverse(
            "lecture-status",
            args=[999999],
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)


    @patch("quizzes.views.enqueue_lecture_processing")
    def test_retry_failed_lecture(self, mock_enqueue):
        self.authenticate(self.professor)

        self.lecture.status = "failed"
        self.lecture.error_message = "Transcription failed."
        self.lecture.save()

        response = self.client.post(self.retry_url)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["error_message"], "")

        self.lecture.refresh_from_db()

        self.assertEqual(self.lecture.status, "pending")
        self.assertEqual(self.lecture.error_message, "")

        mock_enqueue.assert_called_once_with(self.lecture.id)

    @patch("quizzes.views.enqueue_lecture_processing")
    def test_cannot_retry_non_failed_lecture(self, mock_enqueue):
        self.authenticate(self.professor)

        for lecture_status in ["pending", "processing", "ready"]:
            with self.subTest(status=lecture_status):
                self.lecture.status = lecture_status
                self.lecture.save()

                response = self.client.post(self.retry_url)

                self.assertEqual(response.status_code, 400)

                self.lecture.refresh_from_db()
                self.assertEqual(
                    self.lecture.status,
                    lecture_status,
                )

        mock_enqueue.assert_not_called()

    @patch("quizzes.views.enqueue_lecture_processing")
    def test_student_cannot_retry(self, mock_enqueue):
        self.authenticate(self.student)

        self.lecture.status = "failed"
        self.lecture.save()

        response = self.client.post(self.retry_url)

        self.assertEqual(response.status_code, 403)
        mock_enqueue.assert_not_called()

    @patch("quizzes.views.enqueue_lecture_processing")
    def test_other_professor_cannot_retry(self, mock_enqueue):
        self.authenticate(self.other_professor)

        self.lecture.status = "failed"
        self.lecture.save()

        response = self.client.post(self.retry_url)

        self.assertEqual(response.status_code, 403)
        mock_enqueue.assert_not_called()

    def test_retry_unknown_lecture(self):
        self.authenticate(self.professor)

        url = reverse(
            "lecture-retry",
            args=[999999],
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_retry(self):
        response = self.client.post(self.retry_url)

        self.assertEqual(response.status_code, 401)

    @patch(
        "quizzes.views.enqueue_lecture_processing",
        side_effect=OperationalError("Redis unavailable"),
    )
    def test_retry_when_queue_unavailable(self, mock_enqueue):
        self.authenticate(self.professor)

        self.lecture.status = "failed"
        self.lecture.error_message = "Transcription failed."
        self.lecture.save()

        response = self.client.post(self.retry_url)

        self.assertEqual(response.status_code, 503)

        self.lecture.refresh_from_db()

        self.assertEqual(self.lecture.status, "failed")
        self.assertEqual(
            self.lecture.error_message,
            "Transcription failed.",
        )

    @patch(
        "quizzes.views.enqueue_lecture_processing",
        side_effect=RedisError("OOM command not allowed"),
    )
    def test_retry_when_redis_refuses_the_job(self, mock_enqueue):
        # Redis can refuse the job (the stack runs it with noeviction). That is
        # a queue outage too, so the lecture must go back to failed.
        self.authenticate(self.professor)

        self.lecture.status = "failed"
        self.lecture.error_message = "Transcription failed."
        self.lecture.save()

        response = self.client.post(self.retry_url)

        self.assertEqual(response.status_code, 503)

        self.lecture.refresh_from_db()

        self.assertEqual(self.lecture.status, "failed")
        self.assertEqual(self.lecture.error_message, "Transcription failed.")

    @patch(
        "quizzes.views.enqueue_lecture_processing",
        side_effect=ImportError("Tasks unavailable"),
    )
    def test_retry_when_tasks_unavailable(self, mock_enqueue):
        self.authenticate(self.professor)

        self.lecture.status = "failed"
        self.lecture.error_message = "Processing failed."
        self.lecture.save()

        response = self.client.post(self.retry_url)

        self.assertEqual(response.status_code, 503)

        self.lecture.refresh_from_db()

        self.assertEqual(self.lecture.status, "failed")
        self.assertEqual(
            self.lecture.error_message,
            "Processing failed.",
        )
