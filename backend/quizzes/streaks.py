from datetime import date, timedelta

STREAK_BONUS_MIN_RUN = 3
STREAK_BONUS_POINTS = 50


def next_day_streak(count: int, last_day: date | None, today: date) -> int:
    """Return the day streak after an answer on `today`."""
    if last_day is None:
        return 1
    if last_day >= today:
        return count
    if last_day == today - timedelta(days=1):
        return count + 1
    return 1


def current_day_streak(count: int, last_day: date | None, today: date) -> int:
    """Return the day streak to show on `today`."""
    if last_day is None or last_day < today - timedelta(days=1):
        return 0
    return count


def streak_bonus(run: int) -> int:
    """Return the bonus points for a run of correct answers."""
    return STREAK_BONUS_POINTS if run >= STREAK_BONUS_MIN_RUN else 0
