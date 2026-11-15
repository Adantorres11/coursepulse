from celery import chain


def enqueue_lecture_processing(lecture_id):
    from .tasks import (
        transcribe_lecture,
        generate_questions,
    )

    return chain(
        transcribe_lecture.si(lecture_id),
        generate_questions.si(lecture_id),
    ).delay()