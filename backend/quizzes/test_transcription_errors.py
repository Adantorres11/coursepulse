import shutil
import tempfile
from pathlib import Path
from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase, override_settings

from classrooms.models import Classroom
from quizzes import job_errors, media
from quizzes.job_errors import PermanentError, TransientError
from quizzes.jobs import job_logger
from quizzes.media_testing import make_fixture, requires_ffmpeg
from quizzes.models import Lecture, TranscriptChunk
from quizzes.transcription import run_transcription
from quizzes.transcription_testing import SILENCE, SINE, TOKEN, TranscriptionTestMixin, tone


@requires_ffmpeg
class RunTranscriptionErrorTests(TranscriptionTestMixin, TestCase):
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
        for seconds in (5, 30, 60, 65, 180):
            make_fixture(folder, f"tone{seconds}.wav", *SINE, tone(seconds), "-ac", "1")
        make_fixture(folder, "silence60.wav", *SINE, f"{SILENCE}:d=60")
        make_fixture(
            folder, "muted.mp4",
            *SINE, "testsrc=duration=12:size=160x120:rate=10", "-c:v", "mpeg4",
        )
        (folder / "empty.wav").write_bytes(b"")
        (folder / "corrupt.wav").write_bytes(b"this is not a media file" * 100)

    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")

    def run_failing(self, lecture, token=TOKEN):
        """Run the job, expect it to fail and log the WARNING, and return the logs."""
        with self.assertLogs("quizzes.jobs", level="WARNING") as logs:
            self.assertFalse(self.run_job(lecture, token))
        return logs

    def assert_failed(self, lecture, message):
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, message)
        self.assertEqual(lecture.job_token, "")
        self.hand_off.assert_not_called()

    def fail_with(self, name, message, **fields):
        lecture = self.make_lecture(name, **fields)
        self.run_failing(lecture)
        self.assert_failed(lecture, message)
        self.whisper.assert_not_called()
        return lecture

    def test_muted_video_fails_with_no_audio(self):
        self.fail_with("muted.mp4", job_errors.NO_AUDIO)

    def test_zero_byte_fails_immediately(self):
        self.fail_with("empty.wav", job_errors.EMPTY_FILE)

    def test_corrupt_file_fails_with_unreadable(self):
        self.fail_with("corrupt.wav", job_errors.UNREADABLE)

    def test_missing_file_fails_with_not_found(self):
        lecture = self.make_lecture("tone30.wav")
        lecture.recording.name = "lecture_recordings/deleted.wav"
        lecture.save()
        self.run_failing(lecture)
        self.assert_failed(lecture, job_errors.FILE_MISSING)
        self.whisper.assert_not_called()

    def test_too_short_fails(self):
        self.fail_with("tone5.wav", job_errors.TOO_SHORT)

    @override_settings(TRANSCRIPTION_MAX_SECONDS=7200)
    def test_too_long_fails_before_any_whisper_call(self):
        lecture = self.make_lecture("tone30.wav")
        info = media.MediaInfo(duration=9000, audio_index=0, has_video=False)
        with mock.patch("quizzes.media.probe", return_value=info):
            self.run_failing(lecture)
        self.assert_failed(
            lecture, "Recording is longer than 2 hours. Upload a shorter one."
        )
        self.whisper.assert_not_called()

    def test_all_silence_fails_with_no_speech(self):
        self.fail_with("silence60.wav", job_errors.NO_SPEECH)

    def test_repeated_hallucination_fails_with_no_speech(self):
        self.texts = ["Thanks for watching. " * 40]
        lecture = self.make_lecture("tone60.wav")
        self.run_failing(lecture)
        self.assert_failed(lecture, job_errors.NO_SPEECH)

    def test_low_word_rate_fails_incomplete(self):
        self.texts = [" ".join(f"w{i}" for i in range(20))]
        lecture = self.make_lecture("tone180.wav")
        self.run_failing(lecture)
        self.assert_failed(lecture, job_errors.INCOMPLETE)

    @override_settings(TRANSCRIPTION_MAX_COST_USD=0.001)
    def test_cost_cap_refuses_and_logs(self):
        lecture = self.make_lecture("tone30.wav")
        logs = self.run_failing(lecture)
        self.assert_failed(lecture, job_errors.TOO_EXPENSIVE)
        self.whisper.assert_not_called()
        self.assertTrue(any("est_usd" in line for line in logs.output), logs.output)

    def test_missing_key_fails_cleanly(self):
        self.whisper_patch.stop()
        lecture = self.make_lecture("tone30.wav")
        self.run_failing(lecture)
        self.assert_failed(lecture, job_errors.NO_KEY)

    def test_credits_run_out_mid_lecture_keeps_finished_chunks(self):
        def run_out(path, prompt):
            if len(self.prompts) == 2:
                raise PermanentError(job_errors.NO_CREDITS)
            return self.fake_transcribe(path, prompt)

        self.whisper.side_effect = run_out
        lecture = self.make_lecture("tone65.wav")
        with mock.patch("quizzes.transcription.CHUNK_SECONDS", 20):
            self.run_failing(lecture)
            self.assert_failed(lecture, job_errors.NO_CREDITS)
            self.assertEqual(TranscriptChunk.objects.filter(lecture=lecture).count(), 2)

            self.whisper.side_effect = self.fake_transcribe
            self.whisper.reset_mock()
            Lecture.objects.filter(pk=lecture.pk).update(status="pending")
            self.assertTrue(self.run_job(lecture, token="task-2"))
        self.assertEqual(self.whisper.call_count, 1)
        self.assertTrue(lecture.transcript)
        self.assertEqual(TranscriptChunk.objects.count(), 0)
        self.hand_off.assert_called_once_with(lecture.id)

    def test_transient_error_keeps_processing_and_reraises(self):
        def busy(path, prompt):
            if len(self.prompts) == 2:
                raise TransientError(job_errors.SERVICE_BUSY)
            return self.fake_transcribe(path, prompt)

        self.whisper.side_effect = busy
        lecture = self.make_lecture("tone65.wav")
        with mock.patch("quizzes.transcription.CHUNK_SECONDS", 20):
            with self.assertRaises(TransientError):
                run_transcription(lecture.id, TOKEN, 1, job_logger(lecture.id, TOKEN, 1))
        lecture.refresh_from_db()
        self.assertEqual(lecture.status, "processing")
        self.assertEqual(lecture.job_token, TOKEN)
        self.assertEqual(TranscriptChunk.objects.filter(lecture=lecture).count(), 2)

    def test_lecture_deleted_mid_job_exits_quietly(self):
        lecture = self.make_lecture("tone60.wav")

        def delete_then_answer(path, prompt):
            result = self.fake_transcribe(path, prompt)
            Lecture.objects.filter(pk=lecture.pk).delete()
            return result

        self.whisper.side_effect = delete_then_answer
        result = run_transcription(lecture.id, TOKEN, 1, job_logger(lecture.id, TOKEN, 1))
        self.assertFalse(result)
        self.assertFalse(Lecture.objects.filter(pk=lecture.pk).exists())
        self.hand_off.assert_not_called()

    def test_recording_replaced_mid_job_discards_result(self):
        lecture = self.make_lecture("tone60.wav")

        def replace_then_answer(path, prompt):
            result = self.fake_transcribe(path, prompt)
            Lecture.objects.filter(pk=lecture.pk).update(
                recording="lecture_recordings/tone30.wav"
            )
            return result

        self.whisper.side_effect = replace_then_answer
        self.assertFalse(self.run_job(lecture))
        self.assertEqual(lecture.transcript, "")
        self.hand_off.assert_not_called()

    def test_reaper_failed_mid_job_exits_quietly(self):
        lecture = self.make_lecture("tone60.wav")

        def reap_then_answer(path, prompt):
            result = self.fake_transcribe(path, prompt)
            Lecture.objects.filter(pk=lecture.pk).update(
                status="failed", job_token="", error_message=job_errors.INTERRUPTED
            )
            return result

        self.whisper.side_effect = reap_then_answer
        self.assertFalse(self.run_job(lecture))
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, job_errors.INTERRUPTED)
        self.assertEqual(lecture.transcript, "")
        self.hand_off.assert_not_called()

    def test_soft_time_limit_marks_timeout(self):
        self.whisper.side_effect = SoftTimeLimitExceeded()
        paths = self.record_temp_dirs()
        lecture = self.make_lecture("tone30.wav")
        self.run_failing(lecture)
        self.assert_failed(lecture, job_errors.TIMEOUT)
        self.assertEqual(len(paths), 1)
        self.assertFalse(Path(paths[0]).exists())

    def record_temp_dirs(self):
        paths = []
        real = tempfile.TemporaryDirectory

        def recording(*args, **kwargs):
            directory = real(*args, **kwargs)
            paths.append(directory.name)
            return directory

        patcher = mock.patch("quizzes.transcription.tempfile.TemporaryDirectory", recording)
        patcher.start()
        self.addCleanup(patcher.stop)
        return paths

    def test_temp_files_are_removed_on_failure(self):
        self.whisper.side_effect = PermanentError(job_errors.NO_CREDITS)
        paths = self.record_temp_dirs()
        lecture = self.make_lecture("tone30.wav")
        self.run_failing(lecture)
        self.assert_failed(lecture, job_errors.NO_CREDITS)
        self.assertEqual(len(paths), 1)
        self.assertFalse(Path(paths[0]).exists())

    def test_unexpected_error_fails_with_generic_message(self):
        self.whisper.side_effect = ValueError("boom detail")
        lecture = self.make_lecture("tone30.wav")
        logs = self.run_failing(lecture)
        self.assert_failed(lecture, job_errors.UNEXPECTED)
        output = "\n".join(logs.output)
        self.assertIn("Traceback", output)
        self.assertIn("boom detail", output)

    def test_error_message_has_no_traceback(self):
        self.whisper.side_effect = ValueError("boom detail")
        lecture = self.make_lecture("tone30.wav")
        with self.assertLogs("quizzes.jobs", level="ERROR"):
            self.run_job(lecture)
        self.assertEqual(lecture.error_message, job_errors.UNEXPECTED)
        self.assertNotIn("Traceback", lecture.error_message)
        self.assertNotIn("ValueError", lecture.error_message)
