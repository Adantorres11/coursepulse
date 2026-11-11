from django.contrib.auth import get_user_model
from django.db.models import Q, Sum


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
