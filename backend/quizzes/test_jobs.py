from datetime import timedelta
from unittest import mock

import redis
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from classrooms.models import Classroom
from quizzes import jobs
from quizzes.job_errors import SERVICE_BUSY, TransientError
from quizzes.jobs import (
    RELEASE_LUA,
    LostOwnership,
    _lock_key,
    claim_questions,
    claim_transcription,
    fail,
    heartbeat,
    job_logger,
    lecture_lock,
    release_stale_lock,
)
from quizzes.models import Lecture


def fake_factory(set_result=True):
    client = mock.Mock()
    client.set.return_value = set_result
    factory = mock.Mock(return_value=client)
    return factory, client


class JobsTestBase(TestCase):
    def setUp(self):
        classroom = Classroom.objects.create(name="Any Class")
        self.lecture = Lecture.objects.create(classroom=classroom, title="L1")

    def reload(self):
        self.lecture.refresh_from_db()
        return self.lecture


class ClaimTests(JobsTestBase):
    def test_claim_pending_lecture(self):
        self.lecture.error_message = "old"
        self.lecture.save()
        self.assertTrue(claim_transcription(self.lecture.id, "t1"))
        lecture = self.reload()
        self.assertEqual(lecture.status, "processing")
        self.assertEqual(lecture.job_token, "t1")
        self.assertEqual(lecture.error_message, "")
        self.assertEqual(lecture.progress_message, "Checking the recording")
        self.assertIsNotNone(lecture.last_progress_at)

    def test_second_claim_with_other_token_fails(self):
        self.assertTrue(claim_transcription(self.lecture.id, "t1"))
        self.assertFalse(claim_transcription(self.lecture.id, "t2"))
        self.assertEqual(self.reload().job_token, "t1")

    def test_same_token_can_reclaim_after_retry(self):
        self.assertTrue(claim_transcription(self.lecture.id, "t1"))
        self.assertTrue(claim_transcription(self.lecture.id, "t1"))

    def test_claim_refuses_failed_lecture(self):
        Lecture.objects.filter(pk=self.lecture.id).update(status="failed")
        self.assertFalse(claim_transcription(self.lecture.id, "t1"))

    def test_claim_refuses_ready_lecture(self):
        Lecture.objects.filter(pk=self.lecture.id).update(status="ready")
        self.assertFalse(claim_transcription(self.lecture.id, "t1"))

    def test_five_claims_only_one_wins(self):
        results = [claim_transcription(self.lecture.id, f"t{i}") for i in range(5)]
        self.assertEqual(results.count(True), 1)

    def test_claim_questions_needs_transcript_and_free_token(self):
        Lecture.objects.filter(pk=self.lecture.id).update(status="processing")
        self.assertFalse(claim_questions(self.lecture.id, "q1"))
        Lecture.objects.filter(pk=self.lecture.id).update(transcript="Some words here.", job_token="other")
        self.assertFalse(claim_questions(self.lecture.id, "q1"))
        Lecture.objects.filter(pk=self.lecture.id).update(job_token="")
        self.assertTrue(claim_questions(self.lecture.id, "q1"))
        self.assertFalse(claim_questions(self.lecture.id, "q2"))
        lecture = self.reload()
        self.assertEqual(lecture.job_token, "q1")
        self.assertIsNotNone(lecture.last_progress_at)

    def test_claim_questions_own_token_needs_allow_own(self):
        Lecture.objects.filter(pk=self.lecture.id).update(
            status="processing", transcript="Some words here.", job_token="q1"
        )
        self.assertFalse(claim_questions(self.lecture.id, "q1"))
        self.assertTrue(claim_questions(self.lecture.id, "q1", allow_own=True))
        self.assertFalse(claim_questions(self.lecture.id, "q2", allow_own=True))

    def test_lock_key_by_stage(self):
        self.assertEqual(_lock_key(5), "lock:lecture:5")
        self.assertEqual(_lock_key(5, "questions"), "lock:lecture:5:questions")


class HeartbeatAndFailTests(JobsTestBase):
    def test_heartbeat_works_inside_testcase_transaction(self):
        claim_transcription(self.lecture.id, "t1")
        heartbeat(self.lecture.id, "t1", "x")
        self.assertEqual(Lecture.objects.count(), 1)
        self.assertEqual(self.reload().progress_message, "x")

    def test_refresh_db_connection_skips_inside_atomic(self):
        with mock.patch.object(jobs, "close_old_connections") as close:
            jobs.refresh_db_connection()
        close.assert_not_called()

    def test_heartbeat_after_reaper_failed_raises_lost_ownership(self):
        claim_transcription(self.lecture.id, "t1")
        fail(self.lecture.id, "t1", "boom")
        with self.assertRaises(LostOwnership):
            heartbeat(self.lecture.id, "t1", "x")

    def test_heartbeat_on_deleted_lecture_raises_lost_ownership(self):
        claim_transcription(self.lecture.id, "t1")
        self.lecture.delete()
        with self.assertRaises(LostOwnership):
            heartbeat(self.lecture.id, "t1", "x")

    def test_fail_with_token_only_affects_owner(self):
        claim_transcription(self.lecture.id, "t1")
        self.assertFalse(fail(self.lecture.id, "other", "msg"))
        self.assertEqual(self.reload().status, "processing")
        self.assertTrue(fail(self.lecture.id, "t1", "msg"))
        lecture = self.reload()
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, "msg")
        self.assertEqual(lecture.job_token, "")
        self.assertEqual(lecture.progress_message, "")

    def test_fail_with_stale_before_skips_a_job_that_just_reported_progress(self):
        claim_transcription(self.lecture.id, "t1")
        heartbeat(self.lecture.id, "t1", "Preparing audio")
        cutoff = timezone.now() - timedelta(minutes=15)
        self.assertFalse(fail(self.lecture.id, "t1", "msg", stale_before=cutoff))
        lecture = self.reload()
        self.assertEqual(lecture.status, "processing")
        self.assertEqual(lecture.job_token, "t1")
        self.assertEqual(lecture.progress_message, "Preparing audio")

    def test_fail_with_stale_before_fails_a_job_with_old_progress(self):
        claim_transcription(self.lecture.id, "t1")
        Lecture.objects.filter(pk=self.lecture.id).update(
            last_progress_at=timezone.now() - timedelta(minutes=16)
        )
        cutoff = timezone.now() - timedelta(minutes=15)
        self.assertTrue(fail(self.lecture.id, "t1", "msg", stale_before=cutoff))
        self.assertEqual(self.reload().status, "failed")

    def test_fail_without_token_fails_any_owner(self):
        claim_transcription(self.lecture.id, "t1")
        self.assertTrue(fail(self.lecture.id, None, "msg"))
        self.assertEqual(self.reload().status, "failed")


@override_settings(CELERY_TASK_ALWAYS_EAGER=False)
class LockTests(TestCase):
    def test_lock_is_noop_in_eager_mode(self):
        factory, _ = fake_factory()
        with override_settings(CELERY_TASK_ALWAYS_EAGER=True):
            with lecture_lock(7, "t1", client_factory=factory) as acquired:
                self.assertTrue(acquired)
        factory.assert_not_called()

    def test_lock_acquire_and_release_with_lua(self):
        factory, client = fake_factory(True)
        with lecture_lock(7, "t1", client_factory=factory) as acquired:
            self.assertTrue(acquired)
            client.eval.assert_not_called()
        client.eval.assert_called_once_with(RELEASE_LUA, 1, "lock:lecture:7", "t1")
        client.delete.assert_not_called()
        args, kwargs = client.set.call_args
        self.assertEqual(args, ("lock:lecture:7", "t1"))
        self.assertTrue(kwargs["nx"])
        self.assertEqual(kwargs["ex"], settings.CELERY_TASK_TIME_LIMIT + 60)

    def test_lock_held_by_same_token_is_not_released(self):
        factory, client = fake_factory(None)
        with lecture_lock(7, "t1", client_factory=factory) as acquired:
            self.assertFalse(acquired)
        client.eval.assert_not_called()
        client.delete.assert_not_called()

    def test_lock_held_by_other_yields_false(self):
        factory, client = fake_factory(None)
        with lecture_lock(7, "t1", client_factory=factory) as acquired:
            self.assertFalse(acquired)
        client.eval.assert_not_called()

    def test_lock_redis_down_is_temporary(self):
        factory, client = fake_factory()
        client.set.side_effect = redis.exceptions.ConnectionError("down")
        with self.assertRaises(TransientError) as ctx:
            with lecture_lock(7, "t1", client_factory=factory):
                self.fail("body must not run")
        self.assertEqual(ctx.exception.message, SERVICE_BUSY)

    def test_lock_release_error_is_ignored(self):
        factory, client = fake_factory(True)
        client.eval.side_effect = redis.exceptions.ConnectionError("down")
        with self.assertLogs("quizzes.jobs", level="WARNING"):
            with lecture_lock(7, "t1", client_factory=factory) as acquired:
                self.assertTrue(acquired)

    def test_release_stale_lock_uses_compare_and_delete(self):
        factory, client = fake_factory()
        release_stale_lock(7, "dead", client_factory=factory)
        client.eval.assert_called_once_with(RELEASE_LUA, 1, "lock:lecture:7", "dead")
        client.delete.assert_not_called()

    def test_release_stale_lock_is_noop_in_eager_mode(self):
        factory, _ = fake_factory()
        with override_settings(CELERY_TASK_ALWAYS_EAGER=True):
            release_stale_lock(7, "dead", client_factory=factory)
        factory.assert_not_called()

    def test_release_stale_lock_skips_empty_token(self):
        factory, _ = fake_factory()
        release_stale_lock(7, "", client_factory=factory)
        factory.assert_not_called()

    def test_release_stale_lock_ignores_redis_errors(self):
        factory, client = fake_factory()
        client.eval.side_effect = redis.exceptions.ConnectionError("down")
        with self.assertLogs("quizzes.jobs", level="WARNING"):
            release_stale_lock(7, "dead", client_factory=factory)


class LoggerTests(TestCase):
    def test_log_lines_carry_lecture_task_attempt(self):
        with self.assertLogs("quizzes.jobs", level="INFO") as logs:
            job_logger(7, "abc", 2).info("hello chunk=1/3")
        self.assertIn("lecture=7 task=abc attempt=2", logs.output[0])
