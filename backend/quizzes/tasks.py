import logging
import random
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from .job_errors import INTERRUPTED, TransientError
from .jobs import LostOwnership, fail, heartbeat, job_logger, release_stale_lock
from .models import Lecture
from .pipeline import enqueue_lecture_processing
from .question_generation import run_question_generation
from .transcription import hand_off, run_transcription

logger = logging.getLogger(__name__)

STUCK_JOB_MINUTES = 15
STUCK_PENDING_MINUTES = 10


@shared_task(bind=True, ignore_result=True, max_retries=3)
def transcribe_lecture(self, lecture_id):
    retries = self.request.retries
    log = job_logger(lecture_id, self.request.id, retries)
    try:
        run_transcription(lecture_id, self.request.id, retries, log)
    except TransientError as exc:
        if retries >= self.max_retries:
            fail(lecture_id, self.request.id, exc.message)
            return
        try:
            heartbeat(lecture_id, self.request.id, "Waiting to retry")
        except LostOwnership:
            log.info("Lost ownership while waiting to retry; stopping")
            return
        countdown = random.uniform(0, min(300, 30 * 2**retries))
        raise self.retry(exc=exc, countdown=countdown)


@shared_task(bind=True, ignore_result=True, max_retries=3)
def generate_questions(self, lecture_id):
    retries = self.request.retries
    log = job_logger(lecture_id, self.request.id, retries)
    try:
        run_question_generation(lecture_id, self.request.id, retries, log)
    except TransientError as exc:
        if retries >= self.max_retries:
            fail(lecture_id, self.request.id, exc.message)
            return
        try:
            heartbeat(lecture_id, self.request.id, "Waiting to retry")
        except LostOwnership:
            log.info("Lost ownership while waiting to retry; stopping")
            return
        countdown = random.uniform(0, min(300, 30 * 2**retries))
        raise self.retry(exc=exc, countdown=countdown)


@shared_task(ignore_result=True)
def reap_stuck_lectures():
    now = timezone.now()
    job_cutoff = now - timedelta(minutes=STUCK_JOB_MINUTES)
    pending_cutoff = now - timedelta(minutes=STUCK_PENDING_MINUTES)

    stuck = list(
        Lecture.objects.filter(
            status="processing", last_progress_at__lt=job_cutoff
        )
        .exclude(job_token="")
        .values_list("id", "job_token")
    )
    for lecture_id, stale in stuck:
        # Free the dead job's lock first, or a professor retry could not take it.
        release_stale_lock(lecture_id, stale)
        release_stale_lock(lecture_id, stale, stage="questions")
        # The token protects a job that took over. The cutoff protects a job that
        # reported progress since the read above.
        fail(lecture_id, stale, INTERRUPTED, stale_before=job_cutoff)

    lost = list(
        Lecture.objects.filter(
            status="processing", job_token="", last_progress_at__lt=job_cutoff
        )
        .exclude(transcript="")
        .values_list("id", flat=True)
    )
    for lecture_id in lost:
        Lecture.objects.filter(pk=lecture_id).update(last_progress_at=timezone.now())
        hand_off(lecture_id)

    stale_pending = list(
        Lecture.objects.filter(
            status="pending", recording__isnull=False, last_progress_at__lt=pending_cutoff
        )
        .exclude(recording="")
        .values_list("id", flat=True)
    )
    for lecture_id in stale_pending:
        Lecture.objects.filter(pk=lecture_id).update(last_progress_at=timezone.now())
        try:
            enqueue_lecture_processing(lecture_id)
        except (OperationalError, RedisError):
            logger.warning("reaper could not re-queue lecture %s", lecture_id, exc_info=True)

    logger.info(
        "reaper: failed %s stuck jobs, re-ran %s lost hand-offs, re-queued %s pending lectures",
        len(stuck),
        len(lost),
        len(stale_pending),
    )
