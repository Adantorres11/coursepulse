from datetime import date, timedelta

from django.test import SimpleTestCase

from .streaks import current_day_streak, next_day_streak, streak_bonus


class StreakRuleTests(SimpleTestCase):
    today = date(2026, 11, 10)

    def test_first_answer_starts_streak_at_one(self):
        self.assertEqual(next_day_streak(0, None, self.today), 1)

    def test_same_day_repeat_keeps_count(self):
        self.assertEqual(next_day_streak(4, self.today, self.today), 4)

    def test_answer_the_day_after_continues_streak(self):
        yesterday = self.today - timedelta(days=1)
        self.assertEqual(next_day_streak(4, yesterday, self.today), 5)

    def test_missed_day_resets_to_one(self):
        two_days_ago = self.today - timedelta(days=2)
        self.assertEqual(next_day_streak(4, two_days_ago, self.today), 1)

    def test_last_day_in_the_future_keeps_count(self):
        tomorrow = self.today + timedelta(days=1)
        self.assertEqual(next_day_streak(4, tomorrow, self.today), 4)

    def test_current_streak_shows_count_for_today_and_yesterday(self):
        yesterday = self.today - timedelta(days=1)
        self.assertEqual(current_day_streak(4, self.today, self.today), 4)
        self.assertEqual(current_day_streak(4, yesterday, self.today), 4)

    def test_current_streak_is_zero_after_a_missed_day(self):
        two_days_ago = self.today - timedelta(days=2)
        self.assertEqual(current_day_streak(4, two_days_ago, self.today), 0)

    def test_current_streak_is_zero_with_no_history(self):
        self.assertEqual(current_day_streak(0, None, self.today), 0)

    def test_streak_bonus_starts_at_run_three(self):
        self.assertEqual(streak_bonus(2), 0)
        self.assertEqual(streak_bonus(3), 50)
        self.assertEqual(streak_bonus(7), 50)
