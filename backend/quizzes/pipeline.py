import logging

from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from .job_errors import QUEUE_FAILED
from .jobs import fail

logger = logging.getLogger(__name__)


def enqueue_lecture_processing(lecture_id):
    from .tasks import transcribe_lecture

    transcribe_lecture.delay(lecture_id)


def start_lecture_processing(lecture_id: int) -> None:
    try:
        enqueue_lecture_processing(lecture_id)
    except (OperationalError, RedisError):
        logger.warning(
            "Could not queue transcription for lecture %s",
            lecture_id,
            exc_info=True,
        )
        fail(lecture_id, None, QUEUE_FAILED)
