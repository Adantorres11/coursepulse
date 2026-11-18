from importlib import import_module

from django.db import IntegrityError, transaction
from django.test import TestCase

from classrooms.models import Classroom
from .models import Lecture, TranscriptChunk


class TranscriptFieldTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")

    def test_new_lecture_has_empty_transcription_fields(self):
        lecture = Lecture.objects.create(classroom=self.classroom, title="L")
        lecture.refresh_from_db()
        self.assertEqual(lecture.transcript, "")
        self.assertIsNone(lecture.raw_transcript)
        self.assertEqual(lecture.transcript_language, "")
        self.assertEqual(lecture.transcript_source, "")
        self.assertIsNone(lecture.audio_seconds)
        self.assertEqual(lecture.job_token, "")
        self.assertEqual(lecture.progress_message, "")
        self.assertIsNone(lecture.last_progress_at)

    def test_transcript_saves_long_unicode_text(self):
        text = "Café “smart quotes” naïve 你好 مرحبا 🎓 — " * 20000
        lecture = Lecture.objects.create(
            classroom=self.classroom, title="L", transcript=text
        )
        lecture.refresh_from_db()
        self.assertEqual(lecture.transcript, text)

    def test_chunk_index_is_unique_per_lecture(self):
        lecture = Lecture.objects.create(classroom=self.classroom, title="L")
        fields = dict(
            lecture=lecture,
            index=0,
            start_seconds=0.0,
            end_seconds=10.0,
            source_name="a.mp3",
        )
        TranscriptChunk.objects.create(**fields)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TranscriptChunk.objects.create(**fields)

    def test_chunks_are_ordered_by_index(self):
        lecture = Lecture.objects.create(classroom=self.classroom, title="L")
        for index in (2, 0, 1):
            TranscriptChunk.objects.create(
                lecture=lecture,
                index=index,
                start_seconds=index * 10.0,
                end_seconds=index * 10.0 + 10.0,
                source_name="a.mp3",
            )
        self.assertEqual(
            [c.index for c in lecture.transcript_chunks.all()], [0, 1, 2]
        )

    def test_migration_0013_sits_on_0012(self):
        module = import_module("quizzes.migrations.0013_lecture_transcription_fields")
        self.assertEqual(
            module.Migration.dependencies,
            [("quizzes", "0012_lecture_error_message_alter_lecture_status")],
        )
