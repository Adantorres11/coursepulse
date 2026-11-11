from django.test import SimpleTestCase

from .grading import QUESTION_TIME_LIMIT_MS, TIME_GRACE_MS, grade_answer
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

    def test_answer_at_the_end_of_grace_is_correct(self):
        result = grade_answer(
            make_question(), 2, QUESTION_TIME_LIMIT_MS + TIME_GRACE_MS
        )
        self.assertEqual(result, (True, 100))

    def test_answer_after_grace_scores_zero(self):
        result = grade_answer(
            make_question(), 2, QUESTION_TIME_LIMIT_MS + TIME_GRACE_MS + 1
        )
        self.assertEqual(result, (False, 0))

    def test_no_choice_is_never_correct(self):
        question = Question(correct_index=0, difficulty="easy")
        self.assertEqual(grade_answer(question, None, 1000), (False, 0))
