import logging
from unittest import mock

from django.test import TestCase, override_settings
from kombu.exceptions import OperationalError

from classrooms.models import Classroom
from quizzes import job_errors, pipeline, tasks
from quizzes.job_errors import TransientError
from quizzes.models import Lecture
from quizzes.question_testing import QuestionJobMixin
from quizzes.test_question_generation import default_model
from quizzes.transcription import hand_off


class TaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")

    def make_lecture(self, **fields):
        return Lecture.objects.create(classroom=self.classroom, title="Week 3", **fields)

    def run_transcribe(self, lecture, run):
        # Retries run inline here. When eager errors propagate (the default
        # outside Docker), Celery raises Retry out of apply(), so switch that off
        # and the tests behave the same on SQLite and on Postgres.
        with mock.patch("quizzes.tasks.run_transcription", run), mock.patch(
            "random.uniform", return_value=0
        ), override_settings(CELERY_TASK_EAGER_PROPAGATES=False):
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

    def run_generate(self, lecture, run):
        with mock.patch("quizzes.tasks.run_question_generation", run), mock.patch(
            "random.uniform", return_value=0
        ), override_settings(CELERY_TASK_EAGER_PROPAGATES=False):
            tasks.generate_questions.apply(args=[lecture.id], task_id="g1")
        lecture.refresh_from_db()

    def test_generate_transient_error_retries_then_succeeds(self):
        lecture = self.make_lecture(status="processing", transcript="some words", job_token="g1")
        run = mock.Mock(side_effect=[TransientError(job_errors.QUESTIONS_BUSY), True])
        self.run_generate(lecture, run)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(lecture.status, "processing")

    def test_generate_transient_error_after_last_retry_marks_failed(self):
        lecture = self.make_lecture(status="processing", transcript="some words", job_token="g1")
        run = mock.Mock(side_effect=TransientError(job_errors.QUESTIONS_BUSY))
        self.run_generate(lecture, run)
        self.assertEqual(run.call_count, 4)
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, job_errors.QUESTIONS_BUSY)
        self.assertEqual(lecture.job_token, "")

    def test_generate_passes_task_id_as_token(self):
        lecture = self.make_lecture(status="processing", transcript="some words", job_token="g1")
        run = mock.Mock(return_value=True)
        self.run_generate(lecture, run)
        run.assert_called_once_with(lecture.id, "g1", 0, mock.ANY)
        self.assertIsInstance(run.call_args.args[3], logging.LoggerAdapter)

    def test_tasks_ignore_results(self):
        self.assertTrue(tasks.transcribe_lecture.ignore_result)
        self.assertTrue(tasks.generate_questions.ignore_result)


@override_settings(
    QUESTION_WORDS_PER_QUESTION=100,
    QUESTION_MIN_COUNT=4,
    QUESTION_MAX_COUNT=8,
    QUESTION_FLOOR_COUNT=2,
    QUESTION_MAX_COST_USD=0.25,
    QUESTION_MODEL="gpt-6-luna",
)
class DuplicateMessageTests(QuestionJobMixin, TestCase):
    def test_second_message_makes_no_calls(self):
        self.model = default_model()
        lecture = self.make_lecture()
        tasks.generate_questions.apply(args=[lecture.id], task_id="g1")
        lecture.refresh_from_db()
        self.assertEqual(lecture.status, "ready")
        calls = len(self.model.calls)
        before = list(lecture.questions.values_list("id", "prompt"))

        tasks.generate_questions.apply(args=[lecture.id], task_id="g2")

        self.assertEqual(len(self.model.calls), calls)
        self.assertEqual(list(lecture.questions.values_list("id", "prompt")), before)
