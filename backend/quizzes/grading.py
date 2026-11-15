from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Answer, Attempt, DayStreak, QuestionStart, QuizCompletion
from .streaks import next_day_streak, streak_bonus

POINTS_BY_DIFFICULTY = {"easy": 100, "medium": 200, "hard": 300}
QUESTION_TIME_LIMIT_MS = 15000
TIME_GRACE_MS = 1000
DAILY_FULL_POINTS_QUESTIONS = 35
CAPPED_POINTS_PERCENT = 25


class AlreadyAnswered(Exception):
    """The open attempt already has an answer for this question."""


class NotStarted(Exception):
    """The question was not started in the open attempt."""


def grade_answer(question, chosen_index, time_taken_ms):
    """Return (is_correct, points_awarded) for one answer."""
    is_correct = (
        chosen_index is not None
        and chosen_index == question.correct_index
        and time_taken_ms <= QUESTION_TIME_LIMIT_MS + TIME_GRACE_MS
    )
    points = POINTS_BY_DIFFICULTY[question.difficulty] if is_correct else 0
    return is_correct, points


def capped_points(base_points, answers_today):
    """Return the base points, reduced once the daily full-points limit is used."""
    if answers_today < DAILY_FULL_POINTS_QUESTIONS:
        return base_points
    return base_points * CAPPED_POINTS_PERCENT // 100


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


def start_question(user, lecture, question):
    """Record when the user first saw the question. Return (start, created)."""
    with transaction.atomic():
        attempt = get_open_attempt(user, lecture, for_update=True)
        if attempt is None:
            try:
                with transaction.atomic():
                    attempt = Attempt.objects.create(user=user, lecture=lecture)
            except IntegrityError:
                attempt = get_open_attempt(user, lecture, for_update=True)
        if attempt.answers.filter(question=question).exists():
            raise AlreadyAnswered()
        return QuestionStart.objects.get_or_create(
            attempt=attempt, question=question
        )


def submit_answer(user, lecture, question, chosen_index):
    """Save one graded answer on the user's open attempt."""
    now = timezone.now()
    with transaction.atomic():
        attempt = get_open_attempt(user, lecture, for_update=True)
        if attempt is None:
            raise NotStarted()
        start = attempt.starts.filter(question=question).first()
        if start is None:
            raise NotStarted()
        time_taken_ms = int((now - start.started_at).total_seconds() * 1000)
        is_correct, points = grade_answer(question, chosen_index, time_taken_ms)
        if attempt.answers.filter(question=question).exists():
            raise AlreadyAnswered()
        today = timezone.localdate()
        # Locking the day streak row makes one student's answers run one at a
        # time, so two lectures cannot read the same daily count.
        day_streak, _ = DayStreak.objects.select_for_update().get_or_create(
            user=user
        )
        if attempt.is_first:
            answers_today = Answer.objects.filter(
                attempt__user=user,
                attempt__is_first=True,
                answered_at__date=today,
            ).count()
            points = capped_points(points, answers_today)
        attempt.answer_streak = attempt.answer_streak + 1 if is_correct else 0
        if is_correct:
            points += streak_bonus(attempt.answer_streak)
        try:
            with transaction.atomic():
                Answer.objects.create(
                    attempt=attempt,
                    question=question,
                    chosen_index=chosen_index,
                    is_correct=is_correct,
                    time_taken_ms=time_taken_ms,
                    points_awarded=points,
                    answered_at=now,
                )
        except IntegrityError:
            raise AlreadyAnswered()
        attempt.total_points += points
        update_fields = ["total_points", "answer_streak"]
        day_streak.count = next_day_streak(
            day_streak.count, day_streak.last_day, today
        )
        day_streak.last_day = today
        day_streak.save()
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
