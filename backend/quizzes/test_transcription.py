import contextlib
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from classrooms.models import Classroom
from quizzes import job_errors, media
from quizzes.job_errors import PermanentError
from quizzes.jobs import claim_transcription, job_logger
from quizzes.media_testing import make_fixture, requires_ffmpeg
from quizzes.models import Lecture, TranscriptChunk
from quizzes.transcription import run_transcription
from quizzes.whisper_client import WhisperResult

SINE = ["-f", "lavfi", "-i"]
SILENCE = "anullsrc=r=16000:cl=mono"
READY = "Transcript ready. Starting question generation."
TOKEN = "task-1"
real_probe = media.probe
real_normalize = media.normalize_audio


@contextlib.contextmanager
def fake_lock(lecture_id, token):
    yield True


def _concat(*inputs):
    """ffmpeg args that join lavfi inputs into one mono 16 kHz WAV."""
    args = []
    for spec in inputs:
        args += [*SINE, spec]
    labels = "".join(f"[{i}:a]" for i in range(len(inputs)))
    return [
        *args,
        "-filter_complex", f"{labels}concat=n={len(inputs)}:v=0:a=1[o]",
        "-map", "[o]", "-ac", "1", "-ar", "16000",
    ]


def _tone(seconds):
    return f"sine=f=300:d={seconds}:sample_rate=16000"


@requires_ffmpeg
class RunTranscriptionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.media_root, ignore_errors=True)
        cls.media_settings = override_settings(MEDIA_ROOT=str(cls.media_root))
        cls.media_settings.enable()
        cls.addClassCleanup(cls.media_settings.disable)
        folder = cls.media_root / "lecture_recordings"
        folder.mkdir()
        for seconds in (30, 50, 60, 65):
            make_fixture(folder, f"tone{seconds}.wav", *SINE, _tone(seconds), "-ac", "1")
        make_fixture(
            folder, "gap.wav",
            *_concat(_tone(20), f"{SILENCE}:d=180", _tone(20)),
        )
        make_fixture(folder, "lead.wav", *_concat(f"{SILENCE}:d=5", _tone(30)))
        make_fixture(
            folder, "quiet.wav", *SINE, f"{_tone(30)},volume=-22dB", "-ac", "1"
        )

    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")

    def setUp(self):
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

    def plan_for(self, lecture, chunk_seconds):
        silences, duration = media.find_silences(Path(lecture.recording.path), 0)
        start, end = media.speech_bounds(duration, silences)
        return media.plan_chunks(end - start, [], chunk_seconds=chunk_seconds)

    def save_chunk(self, lecture, chunk, text, source=None):
        TranscriptChunk.objects.create(
            lecture=lecture,
            index=chunk.index,
            start_seconds=chunk.start,
            end_seconds=chunk.end,
            source_name=source or lecture.recording.name,
            text=text,
            raw={
                "text": text,
                "language": "english",
                "segments": [{"start": 0.0, "end": 1.0, "text": text}],
            },
        )

    def test_short_recording_success_saves_transcript_and_hands_off(self):
        lecture = self.make_lecture("tone60.wav")
        self.assertTrue(self.run_job(lecture))
        self.assertEqual(lecture.status, "processing")
        self.assertTrue(lecture.transcript)
        self.assertEqual(lecture.transcript_source, lecture.recording.name)
        self.assertAlmostEqual(lecture.audio_seconds, 60, delta=1)
        self.assertEqual(lecture.transcript_language, "english")
        self.assertEqual(lecture.job_token, "")
        self.assertEqual(lecture.error_message, "")
        self.assertEqual(lecture.progress_message, READY)
        self.assertEqual(lecture.raw_transcript["model"], "whisper-1")
        self.hand_off.assert_called_once_with(lecture.id)
        self.assertEqual(TranscriptChunk.objects.count(), 0)
        self.assertEqual(self.whisper.call_count, 1)

    def test_long_recording_is_chunked_and_joined_in_order(self):
        self.texts = [
            "one two three four five alpha beta gamma",
            "alpha beta gamma six seven eight nine",
            "ten eleven twelve thirteen",
        ]
        lecture = self.make_lecture("tone65.wav")
        with mock.patch("quizzes.transcription.CHUNK_SECONDS", 20):
            self.assertTrue(self.run_job(lecture))
        self.assertEqual(self.whisper.call_count, 3)
        self.assertEqual(
            lecture.transcript,
            "one two three four five alpha beta gamma six seven eight nine "
            "ten eleven twelve thirteen",
        )
        segments = lecture.raw_transcript["segments"]
        starts = [s["start"] for s in segments]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(len(set(starts)), len(starts))
        self.assertGreaterEqual(starts[-1], 38)
        self.assertIn("Any Class", self.prompts[1])
        self.assertIn("Week 3 Graphs", self.prompts[1])
        self.assertTrue(self.prompts[1].endswith("alpha beta gamma"))

    def test_small_file_longer_than_chunk_length_is_still_split(self):
        lecture = self.make_lecture("tone50.wav")
        with mock.patch("quizzes.transcription.CHUNK_SECONDS", 20):
            self.assertTrue(self.run_job(lecture))
        self.assertEqual(self.whisper.call_count, 2)
        chunks = lecture.raw_transcript["chunks"]
        self.assertEqual([c["index"] for c in chunks], [0, 1])
        self.assertAlmostEqual(chunks[0]["start"], 0, delta=0.1)
        self.assertAlmostEqual(chunks[0]["end"], 20, delta=0.1)
        self.assertAlmostEqual(chunks[1]["start"], 18, delta=0.1)
        self.assertAlmostEqual(chunks[1]["end"], 50, delta=0.5)

    def test_part_over_safe_bytes_is_refused(self):
        lecture = self.make_lecture("tone30.wav")
        with mock.patch("quizzes.transcription.SAFE_BYTES", 1_000), \
                self.assertLogs("quizzes.jobs", level="INFO") as logs, \
                self.assertRaises(PermanentError) as ctx:
            run_transcription(lecture.id, TOKEN, 1, job_logger(lecture.id, TOKEN, 1))
        self.assertEqual(ctx.exception.message, job_errors.UNEXPECTED)
        self.whisper.assert_not_called()
        self.assertTrue(any("bytes=" in line for line in logs.output), logs.output)

    def test_mid_silence_is_not_cut(self):
        lecture = self.make_lecture("gap.wav")
        self.assertTrue(self.run_job(lecture))
        self.assertAlmostEqual(lecture.audio_seconds, 220, delta=1)
        self.assertEqual(self.whisper.call_count, 1)

    def test_leading_silence_is_trimmed_not_rejected(self):
        lecture = self.make_lecture("lead.wav")
        with mock.patch(
            "quizzes.media.normalize_audio", wraps=real_normalize
        ) as normalize:
            self.assertTrue(self.run_job(lecture))
        start = normalize.call_args.args[2]
        self.assertAlmostEqual(start, 5, delta=0.5)

    def test_quiet_recording_is_not_trimmed_or_rejected(self):
        lecture = self.make_lecture("quiet.wav")
        with mock.patch(
            "quizzes.media.normalize_audio", wraps=real_normalize
        ) as normalize:
            self.assertTrue(self.run_job(lecture))
        start, end = normalize.call_args.args[2:4]
        self.assertAlmostEqual(start, 0, delta=0.1)
        self.assertAlmostEqual(end, 30, delta=1)

    def test_resume_skips_saved_chunks(self):
        lecture = self.make_lecture("tone65.wav")
        plan = self.plan_for(lecture, 20)
        self.assertEqual(len(plan), 3)
        self.save_chunk(lecture, plan[0], "saved first part words here")
        self.save_chunk(lecture, plan[1], "saved second part ends with omega")
        with mock.patch("quizzes.transcription.CHUNK_SECONDS", 20):
            self.assertTrue(self.run_job(lecture))
        self.assertEqual(self.whisper.call_count, 1)
        self.assertTrue(self.prompts[0].endswith("ends with omega"))
        self.assertTrue(lecture.transcript.startswith("saved first part words here saved second"))
        self.assertEqual(TranscriptChunk.objects.count(), 0)

    def test_stale_chunks_from_other_recording_are_discarded(self):
        lecture = self.make_lecture("tone60.wav")
        plan = self.plan_for(lecture, 600)
        self.save_chunk(lecture, plan[0], "STALE text from another file", source="old.mp3")
        self.assertTrue(self.run_job(lecture))
        self.assertEqual(self.whisper.call_count, 1)
        self.assertNotIn("STALE", lecture.transcript)

    def test_retry_with_existing_transcript_skips_whisper(self):
        text = "saved words here from an earlier run of this job"
        lecture = self.make_lecture("tone60.wav", transcript=text, error_message="old")
        lecture.transcript_source = lecture.recording.name
        lecture.save()
        with mock.patch("quizzes.media.probe") as probe, \
                mock.patch("quizzes.media.find_silences") as silences, \
                mock.patch("quizzes.media.normalize_audio") as normalize:
            self.assertTrue(self.run_job(lecture))
        probe.assert_not_called()
        silences.assert_not_called()
        normalize.assert_not_called()
        self.whisper.assert_not_called()
        self.assertEqual(lecture.transcript, text)
        self.assertEqual(lecture.job_token, "")
        self.assertEqual(lecture.error_message, "")
        self.assertEqual(lecture.progress_message, READY)
        self.hand_off.assert_called_once_with(lecture.id)

    def test_reuse_needs_the_claim(self):
        lecture = self.make_lecture(
            "tone60.wav", transcript="saved words", status="processing", job_token="other"
        )
        lecture.transcript_source = lecture.recording.name
        lecture.save()
        self.assertFalse(self.run_job(lecture))
        self.hand_off.assert_not_called()

    def test_duplicate_run_does_nothing(self):
        lecture = self.make_lecture("tone60.wav")
        self.assertTrue(claim_transcription(lecture.id, "other"))
        self.assertFalse(self.run_job(lecture))
        self.whisper.assert_not_called()
        self.hand_off.assert_not_called()

    def test_transcript_never_logged_at_info(self):
        self.text_word = "ZEBRA-SECRET-WORD"
        lecture = self.make_lecture("tone60.wav")
        with self.assertLogs(level="INFO") as logs:
            self.assertTrue(self.run_job(lecture))
        self.assertIn("ZEBRA-SECRET-WORD", lecture.transcript)
        for record in logs.records:
            self.assertNotIn("ZEBRA-SECRET-WORD", record.getMessage())
        self.assertTrue(any("transcript saved words=" in line for line in logs.output))
