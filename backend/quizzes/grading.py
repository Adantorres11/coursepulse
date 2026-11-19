from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Answer, Attempt, DayStreak, QuestionStart, QuizCompletion
from .parts import (
    build_shuffle,
    display_correct_index,
    is_choice_permutation,
    original_choice_index,
    part_sizes,
    questions_for_part,
)
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


class QuestionNotInPart(Exception):
    """The question is not one of the questions in this part."""


class ChoiceOrderMissing(Exception):
    """This part has no saved choice order, so a shuffled answer cannot be graded."""


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


def get_open_attempt(user, lecture, for_update=False, part_index=None):
    """Return the user's newest unfinished attempt for the lecture, or None.

    part_index limits the lookup to one part. Omit it to keep the previous
    behavior: the newest open attempt on the lecture, whichever part it is.
    """
    attempts = Attempt.objects.all()
    if for_update:
        attempts = attempts.select_for_update()
    attempts = attempts.filter(
        user=user, lecture=lecture, completed_at__isnull=True
    )
    if part_index is not None:
        attempts = attempts.filter(part_index=part_index)
    return attempts.order_by("-id").first()


def _part_questions(lecture, part_index):
    questions = list(lecture.questions.order_by("position", "id"))
    try:
        part_questions = questions_for_part(questions, part_index)
    except IndexError:
        raise QuestionNotInPart()
    return questions, part_questions


def open_or_create_part_attempt(user, lecture, part_index, part_questions, shuffle):
    """Return the open attempt for this part, creating it when needed.

    A new shuffled attempt stores question order and choice order once.
    A resume returns that same attempt and does not shuffle again.
    """
    with transaction.atomic():
        attempt = get_open_attempt(
            user, lecture, for_update=True, part_index=part_index
        )
        if attempt is None:
            order = []
            choice_orders = {}
            if shuffle:
                order, choice_orders = build_shuffle(
                    [question.id for question in part_questions]
                )
            try:
                with transaction.atomic():
                    attempt = Attempt.objects.create(
                        user=user,
                        lecture=lecture,
                        part_index=part_index,
                        question_order=order,
                        choice_orders=choice_orders,
                    )
            except IntegrityError:
                attempt = get_open_attempt(
                    user, lecture, for_update=True, part_index=part_index
                )
        elif (
            shuffle
            and not attempt.choice_orders
            and not attempt.answers.exists()
        ):
            order, choice_orders = build_shuffle(
                [question.id for question in part_questions]
            )
            attempt.question_order = order
            attempt.choice_orders = choice_orders
            attempt.save(update_fields=["question_order", "choice_orders"])
        return attempt


def start_question(user, lecture, question, part_index=0, shuffle=False):
    """Record when the user first saw the question. Return (start, created)."""
    _questions, part_questions = _part_questions(lecture, part_index)
    if question.id not in {item.id for item in part_questions}:
        raise QuestionNotInPart()
    with transaction.atomic():
        attempt = open_or_create_part_attempt(
            user, lecture, part_index, part_questions, shuffle
        )
        if attempt.answers.filter(question=question).exists():
            raise AlreadyAnswered()
        return QuestionStart.objects.get_or_create(
            attempt=attempt, question=question
        )


def _mapped_choice(attempt, question, chosen_index, shuffle):
    """Return (original choice index, correct index in the list the student saw)."""
    if not shuffle:
        return chosen_index, question.correct_index
    permutation = (attempt.choice_orders or {}).get(str(question.id))
    if not is_choice_permutation(permutation):
        raise ChoiceOrderMissing()
    try:
        original = original_choice_index(permutation, chosen_index)
    except ValueError:
        raise ChoiceOrderMissing()
    return original, display_correct_index(permutation, question.correct_index)


def _mark_part_complete(attempt, user, lecture, part_questions):
    """Complete the attempt when every question in the part has an answer.

    The lecture counts as finished once every part has a completed attempt.
    """
    part_ids = {question.id for question in part_questions}
    answered_ids = set(attempt.answers.values_list("question_id", flat=True))
    if not part_ids or not part_ids <= answered_ids:
        return False
    attempt.completed_at = timezone.now()
    sizes = part_sizes(lecture.questions.count())
    completed_parts = set(
        Attempt.objects.filter(
            user=user,
            lecture=lecture,
            completed_at__isnull=False,
        ).values_list("part_index", flat=True)
    )
    completed_parts.add(attempt.part_index)
    if all(index in completed_parts for index in range(len(sizes))):
        QuizCompletion.objects.get_or_create(user=user, lecture=lecture)
    return True


def submit_answer(user, lecture, question, chosen_index, part_index=0, shuffle=False):
    """Save one graded answer on the user's open attempt for this part.

    When shuffle is true, chosen_index is the button the student pressed.
    It is mapped through the saved choice order before it is compared to the
    question's correct choice. The stored chosen_index is that original index.
    The returned correct_index is the button index in the shuffled list.
    """
    _questions, part_questions = _part_questions(lecture, part_index)
    if question.id not in {item.id for item in part_questions}:
        raise QuestionNotInPart()
    now = timezone.now()
    with transaction.atomic():
        attempt = get_open_attempt(
            user, lecture, for_update=True, part_index=part_index
        )
        if attempt is None:
            raise NotStarted()
        start = attempt.starts.filter(question=question).first()
        if start is None:
            raise NotStarted()
        time_taken_ms = int((now - start.started_at).total_seconds() * 1000)
        original_index, shown_correct = _mapped_choice(
            attempt, question, chosen_index, shuffle
        )
        is_correct, points = grade_answer(question, original_index, time_taken_ms)
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
                    chosen_index=original_index,
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
        if _mark_part_complete(attempt, user, lecture, part_questions):
            update_fields.append("completed_at")
        attempt.save(update_fields=update_fields)
    return {
        "is_correct": is_correct,
        "points_awarded": points,
        "total_points": attempt.total_points,
        "correct_index": shown_correct,
    }
