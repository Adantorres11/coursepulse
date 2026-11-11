POINTS_BY_DIFFICULTY = {"easy": 100, "medium": 200, "hard": 300}
QUESTION_TIME_LIMIT_MS = 15000


def grade_answer(question, chosen_index, time_taken_ms):
    """Return (is_correct, points_awarded) for one answer."""
    is_correct = (
        chosen_index == question.correct_index
        and time_taken_ms <= QUESTION_TIME_LIMIT_MS
    )
    points = POINTS_BY_DIFFICULTY[question.difficulty] if is_correct else 0
    return is_correct, points
