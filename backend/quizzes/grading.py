from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Answer, Attempt, QuizCompletion

POINTS_BY_DIFFICULTY = {"easy": 100, "medium": 200, "hard": 300}
QUESTION_TIME_LIMIT_MS = 15000


class AlreadyAnswered(Exception):
    """The open attempt already has an answer for this question."""


def grade_answer(question, chosen_index, time_taken_ms):
    """Return (is_correct, points_awarded) for one answer."""
    is_correct = (
        chosen_index == question.correct_index
        and time_taken_ms <= QUESTION_TIME_LIMIT_MS
    )
    points = POINTS_BY_DIFFICULTY[question.difficulty] if is_correct else 0
    return is_correct, points


def get_open_attempt(user, lecture, for_update=False):
    """Return the user's newest unfinished attempt for the lecture, or None."""
    attempts = Attempt.objects.all()
    if for_update:
        attempts = attempts.select_for_update()
    return (
        attempts
        .filter(user=user, lecture=lecture, completed_at__isnull=True)
        .order_by("-id")
        .first()
    )


def submit_answer(user, lecture, question, chosen_index, time_taken_ms):
    """Save one graded answer on the user's open attempt."""
    is_correct, points = grade_answer(question, chosen_index, time_taken_ms)
    with transaction.atomic():
        attempt = get_open_attempt(
            user, lecture, for_update=True
        ) or Attempt.objects.create(user=user, lecture=lecture)
        if attempt.answers.filter(question=question).exists():
            raise AlreadyAnswered()
        try:
            with transaction.atomic():
                Answer.objects.create(
                    attempt=attempt,
                    question=question,
                    chosen_index=chosen_index,
                    is_correct=is_correct,
                    time_taken_ms=time_taken_ms,
                    points_awarded=points,
                )
        except IntegrityError:
            raise AlreadyAnswered()
        attempt.total_points += points
        update_fields = ["total_points"]
        if attempt.answers.count() == lecture.questions.count():
            attempt.completed_at = timezone.now()
            update_fields.append("completed_at")
            QuizCompletion.objects.get_or_create(user=user, lecture=lecture)
        attempt.save(update_fields=update_fields)
    return {
        "is_correct": is_correct,
        "points_awarded": points,
        "total_points": attempt.total_points,
        "correct_index": question.correct_index,
    }
