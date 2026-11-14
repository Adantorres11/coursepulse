from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Profile
from classrooms.models import Classroom, Enrollment
from quizzes.models import Attempt, Answer, Lecture, Question


class ClassResultsTests(APITestCase):
    def setUp(self):
        self.professor = self.create_user(
            "professor", "professor"
        )
        self.other_professor = self.create_user(
            "other_professor", "professor"
        )
        self.student = self.create_user(
            "student", "student"
        )
        self.second_student = self.create_user(
            "student2", "student"
        )

        self.classroom = Classroom.objects.create(
            name="Software Engineering",
            professor=self.professor,
        )

        Enrollment.objects.create(
            user=self.student,
            classroom=self.classroom,
        )
        Enrollment.objects.create(
            user=self.second_student,
            classroom=self.classroom,
        )

        self.lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Lecture 1",
            published_at=timezone.now(),
        )

        self.question = Question.objects.create(
            lecture=self.lecture,
            prompt="What is 2 + 2?",
            choices=["4", "3", "5", "6"],
            correct_index=0,
            difficulty="easy",
            position=1,
        )

        self.url = reverse(
            "class-results",
            args=[self.classroom.id],
        )

    def create_user(self, username, role):
        user = User.objects.create_user(
            username=username,
            password="testpass",
        )
        Profile.objects.create(user=user, role=role)
        return user

    def create_attempt(self, user, question, correct,
                       completed=True):
        points = 100 if correct else 0

        attempt = Attempt.objects.create(
            user=user,
            lecture=question.lecture,
            total_points=points,
            completed_at=(
                timezone.now() if completed else None
            ),
        )

        Answer.objects.create(
            attempt=attempt,
            question=question,
            chosen_index=0 if correct else 1,
            is_correct=correct,
            time_taken_ms=1000,
            points_awarded=points,
        )

        return attempt

    def test_professor_can_view_results(self):
        # First attempt and two retakes.
        self.create_attempt(
            self.student, self.question, True
        )
        self.create_attempt(
            self.student, self.question, True
        )
        self.create_attempt(
            self.student, self.question, False
        )

        # An unfinished attempt should not affect results.
        second_lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Lecture 2",
            published_at=timezone.now(),
        )

        second_question = Question.objects.create(
            lecture=second_lecture,
            prompt="What is 3 + 3?",
            choices=["6", "7", "8", "9"],
            correct_index=0,
            difficulty="easy",
            position=1,
        )

        self.create_attempt(
            self.student,
            second_question,
            True,
            completed=False,
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        students = response.data["students"]
        self.assertEqual(len(students), 2)

        self.assertEqual(students[0]["name"], "student")
        self.assertEqual(students[0]["total_points"], 100)
        self.assertEqual(students[0]["quizzes_played"], 1)

        self.assertEqual(students[1]["total_points"], 0)
        self.assertEqual(students[1]["quizzes_played"], 0)

        lectures = response.data["lectures"]
        self.assertEqual(len(lectures), 2)

        question = lectures[0]["questions"][0]

        self.assertEqual(question["answer_count"], 3)
        self.assertEqual(question["correct_count"], 2)
        self.assertEqual(
            question["accuracy_percent"], 66.67
        )

        unanswered = lectures[1]["questions"][0]
        self.assertEqual(unanswered["answer_count"], 0)
        self.assertIsNone(unanswered["accuracy_percent"])

    def test_empty_class_results(self):
        classroom = Classroom.objects.create(
            name="Empty Class",
            professor=self.professor,
        )

        self.client.force_authenticate(user=self.professor)

        response = self.client.get(
            reverse("class-results", args=[classroom.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["students"], [])
        self.assertEqual(response.data["lectures"], [])

    def test_other_class_results_not_included(self):
        other_class = Classroom.objects.create(
            name="Other Class",
            professor=self.professor,
        )

        Enrollment.objects.create(
            user=self.student,
            classroom=other_class,
        )

        other_lecture = Lecture.objects.create(
            classroom=other_class,
            title="Other Lecture",
        )

        other_question = Question.objects.create(
            lecture=other_lecture,
            prompt="What is 1 + 1?",
            choices=["2", "3", "4", "5"],
            correct_index=0,
            difficulty="easy",
        )

        self.create_attempt(
            self.student, other_question, True
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        student = next(
            item for item in response.data["students"]
            if item["student_id"] == self.student.id
        )

        self.assertEqual(student["total_points"], 0)
        self.assertEqual(student["quizzes_played"], 0)
        self.assertEqual(len(response.data["lectures"]), 1)

    def test_other_professor_cannot_access_results(self):
        self.client.force_authenticate(
            user=self.other_professor
        )
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_results(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unknown_class(self):
        self.client.force_authenticate(user=self.professor)

        response = self.client.get(
            reverse(
                "class-results",
                args=[self.classroom.id + 10000],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)