from django.core.exceptions import ValidationError
from django.test import TestCase

from classrooms.models import Classroom
from .models import Lecture, Question


class QuestionModelTests(TestCase):
    def setUp(self):
        classroom = Classroom.objects.create(name="CS 3398")
        self.lecture = Lecture.objects.create(
            classroom=classroom,
            title="Agile and Scrum",
        )
        self.valid_data = {
            "lecture": self.lecture,
            "prompt": "Which answer is correct?",
            "choices": ["A", "B", "C", "D"],
            "correct_index": 2,
            "difficulty": "easy",
            "position": 0,
        }

    def test_valid_question_is_saved(self):
        question = Question.objects.create(**self.valid_data)
        question.refresh_from_db()
        self.assertEqual(question.choices, ["A", "B", "C", "D"])
        self.assertEqual(question.correct_index, 2)

    def test_choices_must_be_four_strings(self):
        invalid_choices = [
            ["A", "B", "C"],
            ["A", "B", "C", "D", "E"],
            ["A", "B", "C", 4],
            "ABCD",
        ]
        for choices in invalid_choices:
            with self.subTest(choices=choices):
                data = {**self.valid_data, "choices": choices}
                with self.assertRaises(ValidationError):
                    Question.objects.create(**data)

    def test_correct_index_must_be_zero_to_three(self):
        for index in range(4):
            with self.subTest(valid_index=index):
                data = {**self.valid_data, "correct_index": index}
                Question.objects.create(**data)

        for index in (-1, 4):
            with self.subTest(invalid_index=index):
                data = {**self.valid_data, "correct_index": index}
                with self.assertRaises(ValidationError):
                    Question.objects.create(**data)

    def test_difficulty_values(self):
        for difficulty in ("easy", "medium", "hard"):
            with self.subTest(difficulty=difficulty):
                data = {**self.valid_data, "difficulty": difficulty}
                Question.objects.create(**data)

        data = {**self.valid_data, "difficulty": "expert"}
        with self.assertRaises(ValidationError):
            Question.objects.create(**data)

    def test_questions_are_returned_in_position_order(self):
        later = Question.objects.create(
            **{**self.valid_data, "position": 2}
        )
        earlier = Question.objects.create(
            **{**self.valid_data, "position": 1}
        )
        self.assertEqual(
            list(self.lecture.questions.all()),
            [earlier, later],
        )