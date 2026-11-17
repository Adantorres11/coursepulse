import functools
from datetime import timedelta
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone
from kombu.exceptions import OperationalError

from classrooms.models import Classroom
from quizzes import jobs, tasks
from quizzes.job_errors import INTERRUPTED
from quizzes.jobs import RELEASE_LUA, claim_transcription
from quizzes.models import Lecture


def minutes_ago(n):
    return timezone.now() - timedelta(minutes=n)


class ReaperTests(TestCase):
    def setUp(self):
        classroom = Classroom.objects.create(name="Any Class")
        self.classroom = classroom
        patches = {
            name: mock.patch(f"quizzes.tasks.{name}")
            for name in ("enqueue_lecture_processing", "hand_off", "release_stale_lock")
        }
        for name, patcher in patches.items():
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def make(self, **fields):
        return Lecture.objects.create(classroom=self.classroom, title="L1", **fields)

    def reload(self, lecture):
        lecture.refresh_from_db()
        return lecture

    def test_reaper_fails_stuck_processing(self):
        lecture = self.make(status="processing", job_token="t", last_progress_at=minutes_ago(16))
        tasks.reap_stuck_lectures()
        lecture = self.reload(lecture)
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, INTERRUPTED)
        self.assertEqual(lecture.job_token, "")

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_reaper_releases_dead_jobs_lock(self):
        client = mock.Mock()
        factory = mock.Mock(return_value=client)
        lecture = self.make(status="processing", job_token="dead", last_progress_at=minutes_ago(16))
        with mock.patch(
            "quizzes.tasks.release_stale_lock",
            functools.partial(jobs.release_stale_lock, client_factory=factory),
        ):
            tasks.reap_stuck_lectures()
        client.eval.assert_called_once_with(RELEASE_LUA, 1, f"lock:lecture:{lecture.id}", "dead")
        lecture = self.reload(lecture)
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, INTERRUPTED)

    def test_reaper_does_not_overwrite_a_job_that_took_over(self):
        lecture = self.make(status="processing", job_token="old", last_progress_at=minutes_ago(16))

        def take_over(lecture_id, token):
            Lecture.objects.filter(pk=lecture_id).update(
                job_token="new", last_progress_at=timezone.now()
            )

        self.release_stale_lock.side_effect = take_over
        tasks.reap_stuck_lectures()
        lecture = self.reload(lecture)
        self.assertEqual(lecture.status, "processing")
        self.assertEqual(lecture.job_token, "new")

    def test_reaper_then_retry_can_take_the_lock(self):
        lecture = self.make(status="processing", job_token="t", last_progress_at=minutes_ago(16))
        tasks.reap_stuck_lectures()
        self.release_stale_lock.assert_called_once_with(lecture.id, "t")
        Lecture.objects.filter(pk=lecture.id).update(status="pending")
        self.assertTrue(claim_transcription(lecture.id, "t2"))

    def test_reaper_leaves_recent_processing(self):
        lecture = self.make(status="processing", job_token="t", last_progress_at=minutes_ago(5))
        tasks.reap_stuck_lectures()
        lecture = self.reload(lecture)
        self.assertEqual(lecture.status, "processing")
        self.assertEqual(lecture.job_token, "t")
        self.release_stale_lock.assert_not_called()

    def test_reaper_rehands_off_lost_hand_off(self):
        old = minutes_ago(16)
        lecture = self.make(
            status="processing", transcript="some words", job_token="", last_progress_at=old
        )
        tasks.reap_stuck_lectures()
        self.hand_off.assert_called_once_with(lecture.id)
        lecture = self.reload(lecture)
        self.assertEqual(lecture.status, "processing")
        self.assertGreater(lecture.last_progress_at, old)

    def test_reaper_leaves_recent_hand_off(self):
        self.make(
            status="processing", transcript="some words", job_token="", last_progress_at=minutes_ago(5)
        )
        tasks.reap_stuck_lectures()
        self.hand_off.assert_not_called()

    def test_reaper_leaves_questions_stage(self):
        lecture = self.make(
            status="processing",
            transcript="some words",
            job_token="g1",
            last_progress_at=minutes_ago(60),
        )
        tasks.reap_stuck_lectures()
        lecture = self.reload(lecture)
        self.assertEqual(lecture.status, "processing")
        self.assertEqual(lecture.job_token, "g1")
        self.hand_off.assert_not_called()
        self.release_stale_lock.assert_not_called()

    def make_pending_with_recording(self, minutes):
        lecture = self.make(status="pending", last_progress_at=minutes_ago(minutes))
        lecture.recording.save("a.mp3", ContentFile(b"x"), save=False)
        lecture.save()
        return lecture

    def test_reaper_requeues_stale_pending(self):
        lecture = self.make_pending_with_recording(11)
        old = lecture.last_progress_at
        tasks.reap_stuck_lectures()
        self.enqueue_lecture_processing.assert_called_once_with(lecture.id)
        self.assertGreater(self.reload(lecture).last_progress_at, old)

    def test_reaper_ignores_pending_lecture_without_recording(self):
        self.make(status="pending", last_progress_at=minutes_ago(30))
        tasks.reap_stuck_lectures()
        self.enqueue_lecture_processing.assert_not_called()

    def test_reaper_survives_queue_down(self):
        self.make_pending_with_recording(11)
        self.enqueue_lecture_processing.side_effect = OperationalError("down")
        with self.assertLogs("quizzes.tasks", level="WARNING"):
            tasks.reap_stuck_lectures()
