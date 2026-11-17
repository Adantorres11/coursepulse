from unittest.mock import patch

from kombu.exceptions import OperationalError

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import Profile
from classrooms.models import Classroom
from quizzes.models import Lecture


class LectureUploadTests(TestCase):
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

        self.url = reverse(
            "lecture-upload",
            args=[self.classroom.id],
        )

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

    def recording(self, name="lecture.mp3", size=100):
        content = b"ID3" + b"a" * (size - 3)

        return SimpleUploadedFile(
            name,
            content,
            content_type="audio/mpeg",
        )

    @patch("classrooms.views.start_lecture_processing")
    @patch("django.db.models.fields.files.FieldFile.save")
    def test_successful_upload(self, mock_save, mock_start):
        self.authenticate(self.professor)

        response = self.client.post(
            self.url,
            {
                "title": "Introduction",
                "recording": self.recording(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)

        lecture = Lecture.objects.get(
            id=response.data["id"]
        )

        self.assertEqual(lecture.status, "pending")
        self.assertEqual(lecture.title, "Introduction")
        self.assertEqual(lecture.classroom, self.classroom)

    def test_student_cannot_upload(self):
        self.authenticate(self.student)

        response = self.client.post(
            self.url,
            {},
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)

    def test_other_professor_cannot_upload(self):
        self.authenticate(self.other_professor)

        response = self.client.post(
            self.url,
            {},
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_file_type(self):
        self.authenticate(self.professor)

        response = self.client.post(
            self.url,
            {
                "title": "Bad File",
                "recording": self.recording("file.txt"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_content_type(self):
        self.authenticate(self.professor)

        fake_recording = SimpleUploadedFile(
            "lecture.mp3",
            b"fake audio data",
            content_type="image/png",
        )

        response = self.client.post(
            self.url,
            {
                "title": "Invalid Recording",
                "recording": fake_recording,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Lecture.objects.count(), 0)

    @override_settings(LECTURE_UPLOAD_MAX_BYTES=2 * 1024 * 1024)
    def test_oversized_file(self):
        self.authenticate(self.professor)

        large_recording = self.recording(
            size=2 * 1024 * 1024 + 1
        )

        response = self.client.post(
            self.url,
            {
                "title": "Large File",
                "recording": large_recording,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "File must be 2 MB or smaller.",
            str(response.data),
        )
        self.assertEqual(Lecture.objects.count(), 0)

    def test_unknown_class(self):
        self.authenticate(self.professor)

        url = reverse(
            "lecture-upload",
            args=[999999],
        )

        response = self.client.post(
            url,
            {},
            format="multipart",
        )

    def test_invalid_file_signature(self):
        self.authenticate(self.professor)

        fake_recording = SimpleUploadedFile(
            "lecture.mp3",
            b"This is just a text file.",
            content_type="audio/mpeg",
        )

        response = self.client.post(
            self.url,
            {
                "title": "Fake Recording",
                "recording": fake_recording,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Lecture.objects.count(), 0)
        self.assertEqual(response.status_code, 400)

    @patch("classrooms.views.start_lecture_processing")
    @patch("django.db.models.fields.files.FieldFile.save")
    def test_upload_queues_processing_after_commit(self, mock_save, mock_start):
        self.authenticate(self.professor)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                self.url,
                {"title": "Intro", "recording": self.recording()},
                format="multipart",
            )

        mock_start.assert_not_called()

        for callback in callbacks:
            callback()

        mock_start.assert_called_once_with(response.data["id"])

    @patch(
        "quizzes.pipeline.enqueue_lecture_processing",
        side_effect=OperationalError("down"),
    )
    @patch("django.db.models.fields.files.FieldFile.save")
    def test_upload_when_queue_is_down_saves_and_fails_cleanly(
        self, mock_save, mock_enqueue
    ):
        self.authenticate(self.professor)

        with self.assertLogs("quizzes.pipeline", level="WARNING"):
            with patch(
                "classrooms.views.transaction.on_commit",
                side_effect=lambda fn: fn(),
            ):
                response = self.client.post(
                    self.url,
                    {"title": "Intro", "recording": self.recording()},
                    format="multipart",
                )

        self.assertEqual(response.status_code, 201)

        lecture = Lecture.objects.get(id=response.data["id"])

        self.assertEqual(lecture.status, "failed")
        self.assertEqual(
            lecture.error_message,
            "Couldn't start processing, try again.",
        )
        self.assertEqual(response.data["status"], "failed")

    @patch("classrooms.views.start_lecture_processing")
    @patch("django.db.models.fields.files.FieldFile.save")
    def test_accepts_new_formats_with_valid_signatures(self, mock_save, mock_start):
        self.authenticate(self.professor)

        samples = {
            "a.MOV": b"\x00\x00\x00\x14ftypqt  ",
            "a.mkv": b"\x1aE\xdf\xa3" + b"x" * 20,
            "a.webm": b"\x1aE\xdf\xa3" + b"x" * 20,
            "a.avi": b"RIFF\x00\x00\x00\x00AVI LIST",
            "a.ogg": b"OggS" + b"x" * 20,
            "a.flac": b"fLaC" + b"x" * 20,
            "a.aac": b"\xff\xf1" + b"x" * 20,
            "a.M4A": b"\x00\x00\x00\x18ftypM4A ",
        }

        for name, content in samples.items():
            with self.subTest(name=name):
                response = self.client.post(
                    self.url,
                    {
                        "title": name,
                        "recording": SimpleUploadedFile(
                            name, content, content_type="audio/mpeg"
                        ),
                    },
                    format="multipart",
                )

                self.assertEqual(response.status_code, 201)

    @patch("classrooms.views.start_lecture_processing")
    @patch("django.db.models.fields.files.FieldFile.save")
    def test_accepts_odd_browser_content_type(self, mock_save, mock_start):
        self.authenticate(self.professor)

        response = self.client.post(
            self.url,
            {
                "title": "Odd type",
                "recording": SimpleUploadedFile(
                    "lecture.webm",
                    b"\x1aE\xdf\xa3" + b"x" * 20,
                    content_type="application/octet-stream",
                ),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
