import random

from celery import shared_task

from .job_errors import TransientError
from .jobs import LostOwnership, claim_questions, fail, heartbeat, job_logger
from .transcription import run_transcription


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


@shared_task(bind=True, ignore_result=True)
def generate_questions(self, lecture_id):
    log = job_logger(lecture_id, self.request.id, self.request.retries)
    if not claim_questions(lecture_id, self.request.id):
        log.info("generate_questions skipped: lecture is not ready to claim")
        return
    heartbeat(
        lecture_id,
        self.request.id,
        "Transcript ready. Question generation is not built yet.",
    )
    log.info("generate_questions is a placeholder until SCRUM-71")
