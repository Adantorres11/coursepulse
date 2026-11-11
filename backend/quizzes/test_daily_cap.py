from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from classrooms.models import Classroom
from .models import Answer, Attempt, Lecture
from .test_lectures import add_questions
from .testing import answer, make_student


class DailyCapTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")
        cls.user = make_student("student", cls.classroom)

    def setUp(self):
        self.client.force_authenticate(self.user)

    def make_lecture(self, questions):
        lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Lecture",
            published_at=timezone.now() - timedelta(hours=1),
        )
        add_questions(lecture, questions)
        return lecture

    def seed_answers(self, count, is_correct=True, answered_at=None, replay=False):
        """Save earlier answers on one other lecture, without playing them."""
        lecture = self.make_lecture(count)
        if replay:
            Attempt.objects.create(
                user=self.user, lecture=lecture, completed_at=timezone.now()
            )
        attempt = Attempt.objects.create(user=self.user, lecture=lecture)
        for question in lecture.questions.all():
            Answer.objects.create(
                attempt=attempt,
                question=question,
                chosen_index=0,
                is_correct=is_correct,
                time_taken_ms=1000,
                points_awarded=0,
                answered_at=answered_at or timezone.now(),
            )

    def play(self, lecture, position=0):
        question = lecture.questions.get(position=position)
        return answer(self.client, lecture, question, question.correct_index)

    def test_35th_answer_today_earns_full_points(self):
        self.seed_answers(34)
        response = self.play(self.make_lecture(1))
        self.assertEqual(response.json()["points_awarded"], 100)

    def test_36th_answer_today_earns_25_percent(self):
        self.seed_answers(35)
        response = self.play(self.make_lecture(1))
        self.assertEqual(response.json()["points_awarded"], 25)

    def test_wrong_answers_count_toward_cap(self):
        self.seed_answers(35, is_correct=False)
        response = self.play(self.make_lecture(1))
        self.assertEqual(response.json()["points_awarded"], 25)

    def test_streak_bonus_is_not_reduced(self):
        self.seed_answers(35)
        lecture = self.make_lecture(3)
        self.play(lecture, 0)
        self.play(lecture, 1)
        response = self.play(lecture, 2)
        self.assertEqual(response.json()["points_awarded"], 25 + 50)

    def test_answers_from_yesterday_do_not_count(self):
        self.seed_answers(35, answered_at=timezone.now() - timedelta(days=1))
        response = self.play(self.make_lecture(1))
        self.assertEqual(response.json()["points_awarded"], 100)

    def test_replay_answers_do_not_use_the_cap(self):
        self.seed_answers(35, replay=True)
        response = self.play(self.make_lecture(1))
        self.assertEqual(response.json()["points_awarded"], 100)

    def test_replay_is_not_capped(self):
        self.seed_answers(35)
        lecture = self.make_lecture(1)
        first = self.play(lecture)
        response = self.play(lecture)
        self.assertEqual(first.json()["points_awarded"], 25)
        self.assertEqual(response.json()["points_awarded"], 100)
