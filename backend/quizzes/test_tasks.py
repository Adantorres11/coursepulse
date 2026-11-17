from unittest import mock

from django.test import TestCase
from kombu.exceptions import OperationalError

from classrooms.models import Classroom
from quizzes import job_errors, pipeline, tasks
from quizzes.job_errors import TransientError
from quizzes.models import Lecture
from quizzes.transcription import hand_off


class TaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")

    def make_lecture(self, **fields):
        return Lecture.objects.create(classroom=self.classroom, title="Week 3", **fields)

    def run_transcribe(self, lecture, run):
        with mock.patch("quizzes.tasks.run_transcription", run), mock.patch(
            "random.uniform", return_value=0
        ):
            tasks.transcribe_lecture.apply(args=[lecture.id], task_id="t1")
        lecture.refresh_from_db()

    def test_enqueue_sends_only_transcribe(self):
        with mock.patch.object(tasks.transcribe_lecture, "delay") as transcribe, mock.patch.object(
            tasks.generate_questions, "delay"
        ) as generate:
            pipeline.enqueue_lecture_processing(5)
        transcribe.assert_called_once_with(5)
        generate.assert_not_called()

    def test_transient_error_retries_then_succeeds(self):
        lecture = self.make_lecture(status="processing", job_token="t1")
        run = mock.Mock(side_effect=[TransientError(job_errors.SERVICE_BUSY), True])
        self.run_transcribe(lecture, run)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(lecture.status, "processing")

    def test_transient_error_after_last_retry_marks_failed(self):
        lecture = self.make_lecture(status="processing", job_token="t1")
        run = mock.Mock(side_effect=TransientError(job_errors.SERVICE_BUSY))
        self.run_transcribe(lecture, run)
        self.assertEqual(run.call_count, 4)
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, job_errors.SERVICE_BUSY)
        self.assertEqual(lecture.job_token, "")

    def test_permanent_error_never_retries(self):
        lecture = self.make_lecture(status="processing", job_token="t1")

        def run(lecture_id, token, attempt, log):
            Lecture.objects.filter(pk=lecture_id).update(
                status="failed", error_message=job_errors.NO_CREDITS, job_token=""
            )
            return False

        run = mock.Mock(side_effect=run)
        self.run_transcribe(lecture, run)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, job_errors.NO_CREDITS)

    def test_hand_off_queue_failure_keeps_transcript(self):
        lecture = self.make_lecture(status="processing", transcript="some words", job_token="")
        with mock.patch.object(
            tasks.generate_questions, "delay", side_effect=OperationalError("down")
        ), self.assertLogs("quizzes.transcription", level="ERROR"):
            hand_off(lecture.id)
        lecture.refresh_from_db()
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, job_errors.HANDOFF_FAILED)
        self.assertEqual(lecture.transcript, "some words")

    def test_generate_questions_runs_once(self):
        lecture = self.make_lecture(status="processing", transcript="some words", job_token="")
        tasks.generate_questions.apply(args=[lecture.id], task_id="g1")
        tasks.generate_questions.apply(args=[lecture.id], task_id="g2")
        lecture.refresh_from_db()
        self.assertEqual(lecture.job_token, "g1")

    def test_generate_questions_refuses_empty_transcript(self):
        lecture = self.make_lecture(status="processing", transcript="", job_token="")
        tasks.generate_questions.apply(args=[lecture.id], task_id="g1")
        lecture.refresh_from_db()
        self.assertEqual(lecture.job_token, "")

    def test_tasks_ignore_results(self):
        self.assertTrue(tasks.transcribe_lecture.ignore_result)
        self.assertTrue(tasks.generate_questions.ignore_result)
