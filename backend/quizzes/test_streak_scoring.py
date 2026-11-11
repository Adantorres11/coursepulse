from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APITestCase

from classrooms.models import Classroom
from .grading import QUESTION_TIME_LIMIT_MS
from .models import Attempt, DayStreak, Lecture
from .test_lectures import add_questions
from .testing import answer, make_student

DAY = date(2026, 11, 11)


class StreakScoringTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")
        cls.lecture = cls.make_lecture("Lecture", 4)
        cls.user = make_student("student", cls.classroom)

    @classmethod
    def make_lecture(cls, title, questions):
        lecture = Lecture.objects.create(
            classroom=cls.classroom,
            title=title,
            published_at=timezone.now() - timedelta(hours=1),
        )
        add_questions(lecture, questions)
        return lecture

    def setUp(self):
        self.client.force_authenticate(self.user)

    def answer(self, position, correct=True, lecture=None, day=DAY,
               time_taken_ms=4200):
        lecture = lecture or self.lecture
        question = lecture.questions.get(position=position)
        chosen = question.correct_index if correct else question.correct_index + 1
        with patch("quizzes.grading.timezone.localdate", return_value=day):
            if time_taken_ms == 4200:
                return answer(self.client, lecture, question, chosen)
            return self.client.post(
                f"/api/lectures/{lecture.id}/answers/",
                {
                    "question_id": question.id,
                    "chosen_index": chosen,
                    "time_taken_ms": time_taken_ms,
                },
                format="json",
            )

    def test_first_answer_creates_day_streak_of_one(self):
        self.answer(0)
        streak = DayStreak.objects.get(user=self.user)
        self.assertEqual(streak.count, 1)
        self.assertEqual(streak.last_day, DAY)

    def test_second_answer_same_day_keeps_day_streak(self):
        other = self.make_lecture("Other", 1)
        self.answer(0)
        self.answer(0, lecture=other)
        self.assertEqual(DayStreak.objects.get(user=self.user).count, 1)

    def test_answer_next_day_continues_day_streak(self):
        self.answer(0)
        self.answer(1, day=DAY + timedelta(days=1))
        self.assertEqual(DayStreak.objects.get(user=self.user).count, 2)

    def test_answer_after_missed_day_resets_day_streak(self):
        self.answer(0)
        self.answer(1, day=DAY + timedelta(days=2))
        self.assertEqual(DayStreak.objects.get(user=self.user).count, 1)

    def test_correct_answers_build_answer_streak_and_bonus_from_third(self):
        responses = [self.answer(position).json() for position in range(4)]
        self.assertEqual(
            [r["points_awarded"] for r in responses], [100, 100, 150, 150]
        )
        self.assertEqual(responses[-1]["total_points"], 500)
        self.assertEqual(Attempt.objects.get().answer_streak, 4)

    def test_wrong_answer_resets_answer_streak(self):
        results = [
            self.answer(0),
            self.answer(1),
            self.answer(2, correct=False),
            self.answer(3),
        ]
        self.assertEqual(
            [r.json()["points_awarded"] for r in results], [100, 100, 0, 100]
        )
        self.assertEqual(Attempt.objects.get().answer_streak, 1)

    def test_timed_out_correct_answer_resets_answer_streak(self):
        self.answer(0)
        response = self.answer(1, time_taken_ms=QUESTION_TIME_LIMIT_MS + 1)
        self.assertEqual(response.json()["points_awarded"], 0)
        self.assertEqual(Attempt.objects.get().answer_streak, 0)

    def test_resumed_attempt_keeps_answer_streak(self):
        self.answer(0)
        self.answer(1)
        self.client.force_authenticate(self.user)
        response = self.answer(2)
        self.assertEqual(response.json()["points_awarded"], 150)

    def test_replay_attempt_starts_answer_streak_at_zero(self):
        for position in range(4):
            self.answer(position)
        response = self.answer(0)
        self.assertEqual(response.json()["points_awarded"], 100)
        newest = Attempt.objects.order_by("-id").first()
        self.assertEqual(Attempt.objects.count(), 2)
        self.assertEqual(newest.answer_streak, 1)

    def test_rejected_repeat_answer_does_not_change_streaks(self):
        self.answer(0)
        before_day = DayStreak.objects.get(user=self.user).count
        before = Attempt.objects.get()
        response = self.answer(0, day=DAY + timedelta(days=1))
        self.assertEqual(response.status_code, 400)
        after = Attempt.objects.get()
        self.assertEqual(DayStreak.objects.get(user=self.user).count, before_day)
        self.assertEqual(after.answer_streak, before.answer_streak)
        self.assertEqual(after.total_points, before.total_points)
