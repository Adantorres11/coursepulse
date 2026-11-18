"""Ownership helpers for background lecture jobs.

A job owns a lecture while `Lecture.job_token` holds its Celery task id.
Every write below is one guarded UPDATE, so two jobs can never both win.
"""

import logging
from datetime import datetime
from contextlib import contextmanager

import redis
from django.conf import settings
from django.db import close_old_connections, connection
from django.db.models import Q
from django.utils import timezone

from .job_errors import SERVICE_BUSY, TransientError
from .models import Lecture

logger = logging.getLogger(__name__)

RELEASE_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)


class LostOwnership(Exception):
    """The lecture was deleted, failed by the reaper, or claimed by another job."""


def refresh_db_connection() -> None:
    # Closing the connection inside a transaction (Django TestCase) would break it.
    if not connection.in_atomic_block:
        close_old_connections()


def claim_transcription(lecture_id: int, token: str) -> bool:
    updated = Lecture.objects.filter(
        Q(status="pending") | Q(status="processing", job_token=token),
        pk=lecture_id,
    ).update(
        status="processing",
        job_token=token,
        error_message="",
        progress_message="Checking the recording",
        last_progress_at=timezone.now(),
    )
    return updated == 1


def claim_questions(lecture_id: int, token: str) -> bool:
    updated = (
        Lecture.objects.filter(
            Q(job_token="") | Q(job_token=token), pk=lecture_id, status="processing"
        )
        .exclude(transcript="")
        .update(job_token=token, last_progress_at=timezone.now())
    )
    return updated == 1


def heartbeat(lecture_id: int, token: str, message: str) -> None:
    refresh_db_connection()
    updated = Lecture.objects.filter(pk=lecture_id, job_token=token).update(
        progress_message=message,
        last_progress_at=timezone.now(),
    )
    if updated == 0:
        raise LostOwnership(f"lecture {lecture_id} is no longer owned by {token}")


def fail(
    lecture_id: int,
    token: str | None,
    message: str,
    stale_before: datetime | None = None,
) -> bool:
    """Fail the lecture. With `stale_before`, skip a job that reported progress since then."""
    refresh_db_connection()
    lectures = Lecture.objects.filter(pk=lecture_id)
    if token is not None:
        lectures = lectures.filter(job_token=token)
    if stale_before is not None:
        lectures = lectures.filter(last_progress_at__lt=stale_before)
    updated = lectures.update(
        status="failed",
        error_message=message,
        job_token="",
        progress_message="",
        last_progress_at=timezone.now(),
    )
    return updated == 1


def _lock_key(lecture_id: int, stage: str = "") -> str:
    base = f"lock:lecture:{lecture_id}"
    return f"{base}:{stage}" if stage else base


def _client(client_factory):
    return client_factory(settings.CELERY_BROKER_URL, socket_connect_timeout=3, socket_timeout=5)


@contextmanager
def lecture_lock(
    lecture_id: int, token: str, client_factory=redis.Redis.from_url, stage: str = ""
):
    """Yield True when this call holds the lecture lock, False otherwise."""
    if settings.CELERY_TASK_ALWAYS_EAGER:
        yield True
        return
    key = _lock_key(lecture_id, stage)
    try:
        client = _client(client_factory)
        acquired = bool(client.set(key, token, nx=True, ex=settings.CELERY_TASK_TIME_LIMIT + 60))
    except redis.exceptions.RedisError:
        logger.warning("lock acquire failed for lecture %s", lecture_id)
        raise TransientError(SERVICE_BUSY)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                client.eval(RELEASE_LUA, 1, key, token)
            except redis.exceptions.RedisError:
                logger.warning("lock release failed for lecture %s", lecture_id, exc_info=True)


def release_stale_lock(
    lecture_id: int, token: str, client_factory=redis.Redis.from_url, stage: str = ""
) -> None:
    """Free the lock of a job that died without running its `finally`. Never raises."""
    if settings.CELERY_TASK_ALWAYS_EAGER or token == "":
        return
    try:
        _client(client_factory).eval(RELEASE_LUA, 1, _lock_key(lecture_id, stage), token)
    except Exception:
        logger.warning("stale lock release failed for lecture %s", lecture_id, exc_info=True)


class _JobLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        e = self.extra
        return f"lecture={e['lecture']} task={e['task']} attempt={e['attempt']} {msg}", kwargs


def job_logger(lecture_id: int, task_id: str, attempt: int) -> logging.LoggerAdapter:
    return _JobLogAdapter(logger, {"lecture": lecture_id, "task": task_id, "attempt": attempt})
