from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from accounts.usernames import display_username
from quizzes.models import Answer, Attempt, DayStreak
from quizzes.parts import part_sizes
from quizzes.streaks import current_day_streak

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
        )
        .annotate(
            correct_count=Count(
                "answers",
                filter=Q(answers__is_correct=True),
            ),
        )
        .order_by("id")
    )

    # Best completed attempt of each part. Ties keep the lowest attempt id
    # because attempts are ordered by id and a tie does not replace the best.
    # Open attempts are the same query, so a resume flag does not add a round trip.
    best_by_part = {}
    open_parts = set()
    for attempt in attempts:
        key = (attempt.lecture_id, attempt.part_index)
        if attempt.completed_at is None:
            open_parts.add(key)
            continue
        best = best_by_part.get(key)
        if best is None or attempt.total_points > best.total_points:
            best_by_part[key] = attempt

    items = []
    for lecture in lectures:
        sizes = part_sizes(lecture.question_count)
        parts = []
        best_score = 0
        correct_count = 0
        completed_parts = 0
        for index, size in enumerate(sizes):
            best = best_by_part.get((lecture.id, index))
            completed = best is not None
            if completed:
                completed_parts += 1
                best_score += best.total_points
                correct_count += best.correct_count
            parts.append({
                "part": index + 1,
                "question_count": size,
                "completed": completed,
                "best_score": best.total_points if completed else 0,
                "correct_count": best.correct_count if completed else 0,
                "in_progress": (lecture.id, index) in open_parts,
            })
        items.append({
            "id": lecture.id,
            "title": lecture.title,
            "published_at": lecture.published_at,
            "question_count": lecture.question_count,
            "part_count": len(parts),
            "parts": parts,
            # Sum of each part's best attempt. One part keeps the old meaning:
            # the highest completed score for the lecture.
            "best_score": best_score,
            "correct_count": correct_count,
            "is_new": completed_parts == 0,
            "is_complete": len(parts) > 0 and completed_parts == len(parts),
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
        # A quiz here is one part. Replays do not add another played quiz.
        "quizzes_played": sum(
            1 for item in items for part in item["parts"] if part["completed"]
        ),
        "quizzes_total": sum(item["part_count"] for item in items),
        "day_streak": (
            current_day_streak(
                day_streak.count, day_streak.last_day, timezone.localdate()
            )
            if day_streak else 0
        ),
        "answer_streak": newest_attempt.answer_streak if newest_attempt else 0,
        "up_next": next(
            (item for item in items if not item["is_complete"]),
            None,
        ),
        "lectures": items,
    }

def _parts_total(question_count):
    """How many parts a lecture has. A lecture with no questions is one part."""
    count = len(part_sizes(question_count))
    return count if count else 1


def _better_part_attempt(candidate, current):
    """True when candidate should replace the best finished attempt of a part.

    The higher score wins. A tie keeps the earlier attempt.
    """
    if current is None:
        return True
    if candidate.total_points != current.total_points:
        return candidate.total_points > current.total_points
    return candidate.id < current.id


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


def _best_by_part(attempts):
    """Best finished attempt for each student, lecture, and part."""
    best = {}
    for attempt in attempts:
        if attempt.completed_at is None:
            continue
        key = (attempt.user_id, attempt.lecture_id, attempt.part_index)
        if _better_part_attempt(attempt, best.get(key)):
            best[key] = attempt
    return best


def _lecture_play(best_parts, user_id, lecture_id, question_count):
    """Sum the best finished attempt of each part into one lecture score.

    Played means at least one part is finished. The correct count is the sum
    of the correct answers on those same part attempts.
    """
    total_parts = _parts_total(question_count)
    score = 0
    correct_count = 0
    parts_completed = 0
    for part_index in range(total_parts):
        attempt = best_parts.get((user_id, lecture_id, part_index))
        if attempt is None:
            continue
        parts_completed += 1
        score += attempt.total_points
        correct_count += attempt.correct_count
    return {
        "played": parts_completed > 0,
        "score": score if parts_completed else None,
        "correct_count": correct_count if parts_completed else None,
        "parts_completed": parts_completed,
        "parts_total": total_parts,
    }


def _enrolled_student_ids(classroom):
    return list(
        get_user_model().objects.filter(
            enrollments__classroom=classroom,
            profile__role="student",
        ).values_list("id", flat=True)
    )


def _question_counts(classroom):
    return {
        row["id"]: row["question_count"]
        for row in classroom.lectures.annotate(
            question_count=Count("questions"),
        ).values("id", "question_count")
    }


def lecture_row_stats(classroom):
    """Played counts and class averages for every lecture in a class.

    The average uses the same lecture score as the results report: the sum of
    each enrolled student's best finished attempt on each part. Students who
    have not finished a part are left out. Nobody finished means a null average.
    """
    student_ids = _enrolled_student_ids(classroom)
    best_parts = _best_by_part(_completed_attempts(classroom, student_ids))
    question_counts = _question_counts(classroom)
    scores_by_lecture = defaultdict(list)
    seen = set()
    for user_id, lecture_id, _part_index in best_parts:
        if (user_id, lecture_id) in seen:
            continue
        seen.add((user_id, lecture_id))
        play = _lecture_play(
            best_parts,
            user_id,
            lecture_id,
            question_counts.get(lecture_id, 0),
        )
        if play["played"]:
            scores_by_lecture[lecture_id].append(play["score"])

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
        .annotate(question_count=Count("questions"))
        .prefetch_related("questions")
        .order_by("id")
    )


def _first_finished_accuracy(classroom, student_ids, lecture_ids):
    """Count each student once per question, from their first finished answer.

    A replay does not add a second answer. The stored is_correct flag already
    used the original choice index, so a shuffled button order does not change
    the count.
    """
    if not student_ids or not lecture_ids:
        return {}

    answers = (
        Answer.objects.filter(
            attempt__lecture__classroom=classroom,
            attempt__user_id__in=student_ids,
            attempt__lecture_id__in=lecture_ids,
            attempt__completed_at__isnull=False,
        )
        .order_by("attempt__completed_at", "attempt_id", "id")
        .values("question_id", "attempt__user_id", "is_correct")
    )
    seen = set()
    totals = defaultdict(lambda: {"answer_count": 0, "correct_count": 0})
    for row in answers:
        key = (row["attempt__user_id"], row["question_id"])
        if key in seen:
            continue
        seen.add(key)
        bucket = totals[row["question_id"]]
        bucket["answer_count"] += 1
        if row["is_correct"]:
            bucket["correct_count"] += 1
    return totals


def build_class_results(classroom):
    standings = class_standings(classroom)
    student_ids = [standing["user"].id for standing in standings]
    lectures = _published_lectures(classroom)
    lecture_ids = [lecture.id for lecture in lectures]
    best_parts = _best_by_part(
        _completed_attempts(classroom, student_ids, lecture_ids)
    )
    accuracy = _first_finished_accuracy(classroom, student_ids, lecture_ids)

    students = []
    for standing in standings:
        student = standing["user"]
        lecture_rows = []
        played = 0
        for lecture in lectures:
            play = _lecture_play(
                best_parts,
                student.id,
                lecture.id,
                lecture.question_count,
            )
            if play["played"]:
                played += 1
            lecture_rows.append({
                "lecture_id": lecture.id,
                "played": play["played"],
                "score": play["score"],
                "correct_count": play["correct_count"],
                "parts_completed": play["parts_completed"],
                "parts_total": play["parts_total"],
            })
        public_name = display_username(student)
        students.append({
            "student_id": student.id,
            "name": public_name,
            "username": public_name,
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