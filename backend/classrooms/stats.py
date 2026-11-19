from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from quizzes.models import Answer, Attempt, DayStreak
from quizzes.streaks import current_day_streak

from .people import dedicated_username, person_display_name


def class_standings(classroom):
    students = (
        get_user_model().objects
        .filter(
            enrollments__classroom=classroom,
            profile__role="student",
        )
        .select_related("profile")
        .annotate(
            points=Sum(
                "quiz_attempts__total_points",
                filter=Q(
                    quiz_attempts__lecture__classroom=classroom,
                    quiz_attempts__completed_at__isnull=False,
                    quiz_attempts__is_first=True,
                    quiz_attempts__lecture__published_at__lte=timezone.now(),
                ),
                default=0,
            ),
        )
        .order_by("-points", "id")
    )

    standings = []
    previous_points = None
    rank = 0

    for position, student in enumerate(students, start=1):
        if student.points != previous_points:
            rank = position

        standings.append({
            "user": student,
            "points": student.points,
            "rank": rank,
        })

        previous_points = student.points

    return standings


def build_class_stats(classroom, user):
    lectures = (
        classroom.lectures
        .filter(published_at__lte=timezone.now())
        .annotate(question_count=Count("questions"))
        .filter(question_count__gt=0)
        .order_by("-published_at", "-id")
    )

    attempts = (
        Attempt.objects
        .filter(
            user=user,
            lecture__classroom=classroom,
            completed_at__isnull=False,
        )
        .annotate(
            correct_count=Count(
                "answers",
                filter=Q(answers__is_correct=True),
            ),
        )
        .order_by("id")
    )

    best_attempts = {}
    for attempt in attempts:
        best = best_attempts.get(attempt.lecture_id)
        if best is None or attempt.total_points > best.total_points:
            best_attempts[attempt.lecture_id] = attempt

    items = []
    for lecture in lectures:
        best = best_attempts.get(lecture.id)
        items.append({
            "id": lecture.id,
            "title": lecture.title,
            "published_at": lecture.published_at,
            "question_count": lecture.question_count,
            "best_score": best.total_points if best else 0,
            "correct_count": best.correct_count if best else 0,
            "is_new": best is None,
        })

    standings = class_standings(classroom)
    mine = next(s for s in standings if s["user"].pk == user.pk)
    points_above = [
        s["points"] for s in standings if s["points"] > mine["points"]
    ]

    day_streak = DayStreak.objects.filter(user=user).first()
    newest_attempt = (
        Attempt.objects
        .filter(user=user, lecture__classroom=classroom)
        .order_by("-id")
        .first()
    )

    return {
        "classroom_id": classroom.pk,
        "classroom": classroom.name,
        "total_points": mine["points"],
        "rank": mine["rank"],
        "points_to_next_rank": (
            min(points_above) - mine["points"] if points_above else 0
        ),
        "quizzes_played": sum(1 for item in items if not item["is_new"]),
        "quizzes_total": len(items),
        "day_streak": (
            current_day_streak(
                day_streak.count, day_streak.last_day, timezone.localdate()
            )
            if day_streak else 0
        ),
        "answer_streak": newest_attempt.answer_streak if newest_attempt else 0,
        "up_next": next(
            (item for item in items if item["is_new"]),
            None,
        ),
        "lectures": items,
    }

def counted_attempt(attempts):
    """The play that stands for one lecture.

    A lecture is one quiz today, so this is the completed attempt with the
    highest score. A tie keeps the earliest attempt. If a lecture is later
    split into quiz parts, combine the parts here and still return one score
    and one correct count. Callers treat that pair as the lecture total.
    """
    if not attempts:
        return None
    return max(attempts, key=lambda attempt: (attempt.total_points, -attempt.id))


def _mean_score(scores):
    if not scores:
        return None
    rounded = round(sum(scores) / len(scores), 2)
    if rounded == int(rounded):
        return int(rounded)
    return rounded


def _completed_attempts(classroom, student_ids, lecture_ids=None):
    if not student_ids:
        return []
    if lecture_ids is not None and not lecture_ids:
        return []

    filters = {
        "lecture__classroom": classroom,
        "user_id__in": student_ids,
        "completed_at__isnull": False,
    }
    if lecture_ids is not None:
        filters["lecture_id__in"] = lecture_ids

    return list(
        Attempt.objects.filter(**filters).annotate(
            correct_count=Count(
                "answers",
                filter=Q(answers__is_correct=True),
            ),
        )
    )


def _best_by_student_and_lecture(attempts):
    grouped = defaultdict(list)
    for attempt in attempts:
        grouped[(attempt.user_id, attempt.lecture_id)].append(attempt)

    best = {}
    for key, group in grouped.items():
        chosen = counted_attempt(group)
        if chosen is not None:
            best[key] = chosen
    return best


def _enrolled_student_ids(classroom):
    return list(
        get_user_model().objects.filter(
            enrollments__classroom=classroom,
            profile__role="student",
        ).values_list("id", flat=True)
    )


def lecture_row_stats(classroom):
    """Played counts and class averages for every lecture in a class.

    The average uses the same lecture score as the results report: each
    enrolled student's best completed attempt. Students who have not finished
    are left out of the average. Nobody finished means a null average.
    """
    attempts = _completed_attempts(classroom, _enrolled_student_ids(classroom))
    scores_by_lecture = defaultdict(list)
    for attempt in _best_by_student_and_lecture(attempts).values():
        scores_by_lecture[attempt.lecture_id].append(attempt.total_points)

    return {
        lecture_id: {
            "students_played": len(scores),
            "class_average": _mean_score(scores),
        }
        for lecture_id, scores in scores_by_lecture.items()
    }


def _published_lectures(classroom):
    return list(
        classroom.lectures.filter(
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )
        .prefetch_related("questions")
        .order_by("id")
    )


def _question_accuracy(best_attempts):
    attempt_ids = [attempt.id for attempt in best_attempts]
    if not attempt_ids:
        return {}

    rows = (
        Answer.objects.filter(attempt_id__in=attempt_ids)
        .values("question_id")
        .annotate(
            answer_count=Count("attempt__user_id", distinct=True),
            correct_count=Count(
                "attempt__user_id",
                filter=Q(is_correct=True),
                distinct=True,
            ),
        )
    )
    return {row["question_id"]: row for row in rows}


def build_class_results(classroom):
    standings = class_standings(classroom)
    student_ids = [standing["user"].id for standing in standings]
    lectures = _published_lectures(classroom)
    lecture_ids = [lecture.id for lecture in lectures]
    best = _best_by_student_and_lecture(
        _completed_attempts(classroom, student_ids, lecture_ids)
    )
    accuracy = _question_accuracy(best.values())

    students = []
    for standing in standings:
        student = standing["user"]
        lecture_rows = []
        played = 0
        for lecture in lectures:
            attempt = best.get((student.id, lecture.id))
            if attempt is None:
                lecture_rows.append({
                    "lecture_id": lecture.id,
                    "played": False,
                    "score": None,
                    "correct_count": None,
                })
                continue
            played += 1
            lecture_rows.append({
                "lecture_id": lecture.id,
                "played": True,
                "score": attempt.total_points,
                "correct_count": attempt.correct_count,
            })
        students.append({
            "student_id": student.id,
            "name": person_display_name(student),
            "username": dedicated_username(student),
            "total_points": standing["points"],
            "quizzes_played": played,
            "lectures": lecture_rows,
        })

    lecture_rows = []
    for lecture in lectures:
        questions = []
        for question in lecture.questions.all():
            result = accuracy.get(question.id, {})
            answer_count = result.get("answer_count", 0)
            correct_count = result.get("correct_count", 0)
            questions.append({
                "question_id": question.id,
                "prompt": question.prompt,
                "answer_count": answer_count,
                "correct_count": correct_count,
                "accuracy_percent": (
                    round(correct_count / answer_count * 100, 2)
                    if answer_count
                    else None
                ),
            })
        lecture_rows.append({
            "lecture_id": lecture.id,
            "title": lecture.title,
            "questions": questions,
        })

    return {
        "classroom_id": classroom.id,
        "classroom": classroom.name,
        "students": students,
        "lectures": lecture_rows,
    }