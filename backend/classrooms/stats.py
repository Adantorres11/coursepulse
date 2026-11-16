from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from quizzes.models import Attempt, DayStreak
from quizzes.streaks import current_day_streak


def class_standings(classroom):
    students = (
        get_user_model().objects
        .filter(
            enrollments__classroom=classroom,
            profile__role="student",
        )
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
