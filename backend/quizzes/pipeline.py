def enqueue_lecture_processing(lecture_id):
    from .tasks import transcribe_lecture

    transcribe_lecture.delay(lecture_id)
