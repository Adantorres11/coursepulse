from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
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

    @patch("django.db.models.fields.files.FieldFile.save")
    def test_successful_upload(self, mock_save):
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

    def test_oversized_file(self):
        self.authenticate(self.professor)

        large_recording = self.recording(
            size=100 * 1024 * 1024 + 1
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