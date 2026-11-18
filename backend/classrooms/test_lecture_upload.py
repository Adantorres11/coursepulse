import shutil
import tempfile
from unittest.mock import patch

from kombu.exceptions import OperationalError

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from accounts.models import Profile
from classrooms.models import Classroom
from quizzes.models import Lecture


class LectureUploadTestBase(TestCase):
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


class LectureUploadTests(LectureUploadTestBase):
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
        self.assertEqual(
            response.data["recording"],
            [
                "Only MP3, MP4, M4A, WAV, MOV, MKV, WEBM, AVI, "
                "OGG, FLAC, and AAC files are allowed."
            ],
        )
        self.assertEqual(Lecture.objects.count(), 0)

    def test_bad_contents_rejected_whatever_the_content_type(self):
        # The content type is not checked any more. This file is refused
        # because its first bytes are not audio.
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
        self.assertEqual(
            response.data["recording"],
            ["Invalid audio or video file."],
        )
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

        self.assertEqual(response.status_code, 404)

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
        self.assertEqual(
            response.data["recording"],
            ["Invalid audio or video file."],
        )
        self.assertEqual(Lecture.objects.count(), 0)

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


class LectureUploadSavesFileTests(LectureUploadTestBase):
    """Uploads that really write the file, into a throwaway media folder."""

    def setUp(self):
        super().setUp()
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)

    def post_recording(self, name, content, content_type):
        self.authenticate(self.professor)
        return self.client.post(
            self.url,
            {
                "title": "Lecture",
                "recording": SimpleUploadedFile(
                    name,
                    content,
                    content_type=content_type,
                ),
            },
            format="multipart",
        )

    def test_accepts_generic_content_type(self):
        # curl and some browsers send application/octet-stream for audio.
        # The extension and the file signature decide, not this header.
        response = self.post_recording(
            "lecture.mp3",
            b"ID3" + b"a" * 97,
            "application/octet-stream",
        )

        self.assertEqual(response.status_code, 201)

    def test_accepts_other_wav_content_type(self):
        response = self.post_recording(
            "lecture.wav",
            b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 20,
            "audio/vnd.wave",
        )

        self.assertEqual(response.status_code, 201)

    def test_default_limit_fits_a_full_lecture(self):
        # Real 75-minute lecture recordings are 200+ MB (lecture 4 is 239 MB).
        self.assertGreaterEqual(
            settings.LECTURE_UPLOAD_MAX_BYTES,
            1024 * 1024 * 1024,
        )

    @override_settings(LECTURE_UPLOAD_MAX_BYTES=2 * 1024 * 1024)
    def test_accepts_file_at_the_limit(self):
        response = self.post_recording(
            "lecture.mp3",
            b"ID3" + b"a" * (2 * 1024 * 1024 - 3),
            "audio/mpeg",
        )

        self.assertEqual(response.status_code, 201)

    @override_settings(LECTURE_UPLOAD_MAX_BYTES=2 * 1024 * 1024)
    def test_rejects_file_over_the_limit_with_the_limit_in_mb(self):
        response = self.post_recording(
            "lecture.mp3",
            b"ID3" + b"a" * (2 * 1024 * 1024 - 2),
            "audio/mpeg",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["recording"],
            ["File must be 2 MB or smaller."],
        )
        self.assertEqual(Lecture.objects.count(), 0)

    def test_saves_the_recording_on_the_lecture(self):
        content = b"ID3" + b"a" * 97
        response = self.post_recording("lecture.mp3", content, "audio/mpeg")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data,
            {"id": response.data["id"], "title": "Lecture", "status": "pending"},
        )
        lecture = Lecture.objects.get(id=response.data["id"])
        self.assertTrue(lecture.recording.name.startswith("lecture_recordings/"))
        with lecture.recording.open("rb") as saved:
            self.assertEqual(saved.read(), content)
        self.assertIsNone(lecture.published_at)

    def test_accepts_each_allowed_format(self):
        samples = {
            "talk.mp3": b"ID3" + b"\x00" * 20,
            "talk.MP3": b"\xff\xfb" + b"\x00" * 20,
            "talk.wav": b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 20,
            "talk.m4a": b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 20,
            "talk.mp4": b"\x00\x00\x00\x20ftypisom" + b"\x00" * 20,
        }

        for name, content in samples.items():
            with self.subTest(name=name):
                response = self.post_recording(
                    name,
                    content,
                    "application/octet-stream",
                )
                self.assertEqual(response.status_code, 201, response.data)

        self.assertEqual(Lecture.objects.count(), len(samples))

    def test_unauthenticated_upload(self):
        response = self.client.post(
            self.url,
            {
                "title": "Lecture",
                "recording": self.recording(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Lecture.objects.count(), 0)

    def test_missing_title(self):
        self.authenticate(self.professor)

        response = self.client.post(
            self.url,
            {"recording": self.recording()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.data)
        self.assertEqual(Lecture.objects.count(), 0)

    def test_missing_recording(self):
        self.authenticate(self.professor)

        response = self.client.post(
            self.url,
            {"title": "Lecture"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("recording", response.data)
        self.assertEqual(Lecture.objects.count(), 0)

    def test_other_professor_upload_creates_nothing(self):
        self.authenticate(self.other_professor)

        response = self.client.post(
            self.url,
            {
                "title": "Lecture",
                "recording": self.recording(),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Lecture.objects.count(), 0)


class LectureStatusChoicesTests(TestCase):
    def test_status_values_match_the_api_contract(self):
        # SCRUM-72 and the professor class page use pending, processing,
        # ready, and failed. "completed" is not one of them.
        choices = [value for value, _ in Lecture._meta.get_field("status").choices]

        self.assertEqual(
            choices,
            ["pending", "processing", "ready", "failed"],
        )
