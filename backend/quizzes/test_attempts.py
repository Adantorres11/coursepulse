from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from classrooms.models import Classroom
from .models import Answer, Attempt, Lecture, Question


class AttemptAnswerModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="quiz_student",
            password="test-password",
        )
        cls.classroom = Classroom.objects.create(name="CS 3398")
        cls.lecture = Lecture.objects.create(
            classroom=cls.classroom,
            title="Agile and Scrum",
        )
        cls.question = Question.objects.create(
            lecture=cls.lecture,
            prompt="Which answer is correct?",
            choices=["A", "B", "C", "D"],
            correct_index=2,
            difficulty="easy",
            position=0,
        )
        cls.second_question = Question.objects.create(
            lecture=cls.lecture,
            prompt="Which answer is correct next?",
            choices=["A", "B", "C", "D"],
            correct_index=1,
            difficulty="medium",
            position=1,
        )

    def create_answer(self, attempt, **overrides):
        data = {
            "attempt": attempt,
            "question": self.question,
            "chosen_index": 2,
            "is_correct": True,
            "time_taken_ms": 2500,
            "points_awarded": 100,
        }
        data.update(overrides)
        return Answer.objects.create(**data)

    def test_new_attempt_is_incomplete_with_zero_points(self):
        attempt = Attempt.objects.create(
            user=self.user,
            lecture=self.lecture,
        )
        attempt.refresh_from_db()

        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.lecture, self.lecture)
        self.assertIsNotNone(attempt.started_at)
        self.assertIsNone(attempt.completed_at)
        self.assertEqual(attempt.total_points, 0)

    def test_completed_attempt_and_answers_are_persisted(self):
        attempt = Attempt.objects.create(
            user=self.user,
            lecture=self.lecture,
        )
        correct_answer = self.create_answer(attempt)
        incorrect_answer = self.create_answer(
            attempt,
            question=self.second_question,
            chosen_index=0,
            is_correct=False,
            time_taken_ms=4000,
            points_awarded=0,
        )

        completed_at = timezone.now()
        attempt.completed_at = completed_at
        attempt.total_points = 100
        attempt.save(update_fields=["completed_at", "total_points"])

        attempt.refresh_from_db()
        correct_answer.refresh_from_db()
        incorrect_answer.refresh_from_db()

        self.assertEqual(attempt.answers.count(), 2)
        self.assertEqual(attempt.completed_at, completed_at)
        self.assertEqual(attempt.total_points, 100)
        self.assertEqual(correct_answer.chosen_index, 2)
        self.assertTrue(correct_answer.is_correct)
        self.assertEqual(correct_answer.time_taken_ms, 2500)
        self.assertEqual(correct_answer.points_awarded, 100)
        self.assertFalse(incorrect_answer.is_correct)
        self.assertEqual(incorrect_answer.points_awarded, 0)

    def test_duplicate_question_in_same_attempt_is_rejected(self):
        attempt = Attempt.objects.create(
            user=self.user,
            lecture=self.lecture,
        )
        self.create_answer(attempt)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_answer(attempt)

        self.assertEqual(attempt.answers.count(), 1)

    def test_same_question_is_allowed_in_another_attempt(self):
        first_attempt = Attempt.objects.create(
            user=self.user,
            lecture=self.lecture,
        )
        second_attempt = Attempt.objects.create(
            user=self.user,
            lecture=self.lecture,
        )

        self.create_answer(first_attempt)
        self.create_answer(second_attempt)

        self.assertEqual(first_attempt.answers.count(), 1)
        self.assertEqual(second_attempt.answers.count(), 1)

    def test_chosen_index_outside_choices_is_rejected(self):
        attempt = Attempt.objects.create(
            user=self.user,
            lecture=self.lecture,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_answer(attempt, chosen_index=4)

    def test_validation_rejects_question_from_another_lecture(self):
        other_lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Another quiz",
        )
        attempt = Attempt.objects.create(
            user=self.user,
            lecture=other_lecture,
        )
        answer = Answer(
            attempt=attempt,
            question=self.question,
            chosen_index=2,
            is_correct=True,
            time_taken_ms=2500,
            points_awarded=100,
        )

        with self.assertRaises(ValidationError):
            answer.full_clean()

    def test_models_are_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(Attempt))
        self.assertTrue(admin.site.is_registered(Answer))