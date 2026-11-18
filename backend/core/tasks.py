"""Sample Celery task that proves the worker runs.

Real pipeline tasks go in a tasks.py inside the app that owns their data.
The design is in the README section "Lecture pipeline".
"""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task
def ping() -> str:
    logger.info("ping task ran")
    return "pong"
