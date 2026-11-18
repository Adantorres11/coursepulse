"""Shared fixtures for the run_transcription tests."""

import contextlib
from unittest import mock

from quizzes import media
from quizzes.jobs import job_logger
from quizzes.models import Lecture
from quizzes.transcription import run_transcription
from quizzes.whisper_client import WhisperResult

SINE = ["-f", "lavfi", "-i"]
SILENCE = "anullsrc=r=16000:cl=mono"
READY = "Transcript ready. Starting question generation."
TOKEN = "task-1"
real_probe = media.probe


@contextlib.contextmanager
def fake_lock(lecture_id, token):
    yield True


def tone(seconds):
    return f"sine=f=300:d={seconds}:sample_rate=16000"


class TranscriptionTestMixin:
    """Patches the lock, Whisper, and hand-off. Needs `self.classroom` from the test class."""

    def setUp(self):
        super().setUp()
        self.prompts = []
        self.texts = []
        self.text_word = "word"
        patches = [
            mock.patch("quizzes.transcription.lecture_lock", fake_lock),
            mock.patch(
                "quizzes.transcription.transcribe_chunk", side_effect=self.fake_transcribe
            ),
            mock.patch("quizzes.transcription.hand_off"),
        ]
        started = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        self.whisper_patch = patches[1]
        self.whisper, self.hand_off = started[1], started[2]

    def fake_transcribe(self, path, prompt):
        """Return 150 words per minute of part length, in English."""
        self.prompts.append(prompt)
        duration = real_probe(path).duration
        call = len(self.prompts)
        if self.texts:
            text = self.texts.pop(0)
        else:
            count = max(1, round(duration / 60 * 150))
            text = " ".join(f"{self.text_word}{call}x{i}" for i in range(count))
        words = text.split()
        half = len(words) // 2
        segments = [
            {"start": 0.0, "end": duration / 2, "text": " ".join(words[:half])},
            {"start": duration / 2, "end": duration, "text": " ".join(words[half:])},
        ]
        raw = {"text": text, "language": "english", "duration": duration, "segments": segments}
        return WhisperResult(text, "english", duration, segments, raw)

    def make_lecture(self, name, **fields):
        lecture = Lecture.objects.create(
            classroom=self.classroom, title="Week 3 Graphs", **fields
        )
        lecture.recording.name = f"lecture_recordings/{name}"
        lecture.save()
        return lecture

    def run_job(self, lecture, token=TOKEN):
        with self.captureOnCommitCallbacks(execute=True):
            result = run_transcription(
                lecture.id, token, 1, job_logger(lecture.id, token, 1)
            )
        lecture.refresh_from_db()
        return result
