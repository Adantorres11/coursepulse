from django.test import SimpleTestCase

from .grading import QUESTION_TIME_LIMIT_MS, grade_answer
from .models import Question


def make_question(difficulty="easy"):
    return Question(correct_index=2, difficulty=difficulty)


class GradeAnswerTests(SimpleTestCase):
    def test_correct_answer_earns_points_by_difficulty(self):
        for difficulty, points in (("easy", 100), ("medium", 200), ("hard", 300)):
            with self.subTest(difficulty=difficulty):
                result = grade_answer(make_question(difficulty), 2, 1000)
                self.assertEqual(result, (True, points))

    def test_wrong_answer_earns_zero(self):
        result = grade_answer(make_question(), 1, 1000)
        self.assertEqual(result, (False, 0))

    def test_timeout_with_correct_index_scores_zero(self):
        result = grade_answer(make_question(), 2, QUESTION_TIME_LIMIT_MS + 1)
        self.assertEqual(result, (False, 0))

    def test_answer_at_the_limit_is_not_a_timeout(self):
        result = grade_answer(make_question(), 2, QUESTION_TIME_LIMIT_MS)
        self.assertEqual(result, (True, 100))
