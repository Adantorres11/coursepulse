from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Profile
from quizzes.models import Lecture, Question, QuizCompletion

from .models import Classroom, Enrollment

User = get_user_model()


class StudentClassListTests(APITestCase):
    def setUp(self):
        self.student = self.make_user("student", "student")
        self.other_student = self.make_user("other", "student")
        self.professor = self.make_user("professor", "professor")
        self.professor.first_name = "Alex"
        self.professor.last_name = "Smith"
        self.professor.save()

        self.classroom = Classroom.objects.create(
            name="Software Engineering",
            course_code="CS 3398",
            professor=self.professor,
        )
        self.other_classroom = Classroom.objects.create(
            name="Other Class",
            course_code="CS 1000",
        )
        Enrollment.objects.create(
            user=self.student,
            classroom=self.classroom,
        )
        Enrollment.objects.create(
            user=self.other_student,
            classroom=self.other_classroom,
        )
        self.login_as(self.student)

    def make_user(self, username, role):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="Maple!River82",
        )
        Profile.objects.create(user=user, role=role)
        return user

    def login_as(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

    def make_quiz(self, title, published_at, question_count=1):
        lecture = Lecture.objects.create(
            classroom=self.classroom,
            title=title,
            published_at=published_at,
        )
        for position in range(question_count):
            Question.objects.create(
                lecture=lecture,
                prompt=f"Question {position}",
                choices=["A", "B", "C", "D"],
                correct_index=0,
                difficulty="easy",
                position=position,
            )
        return lecture

    def test_returns_only_enrolled_classes(self):
        response = self.client.get("/api/classes/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0], {
            "id": self.classroom.id,
            "name": "Software Engineering",
            "course_code": "CS 3398",
            "professor": {
                "id": self.professor.id,
                "name": "Alex Smith",
            },
            "quiz_count": 0,
            "new_quiz_count": 0,
        })

    def test_student_without_classes_gets_empty_list(self):
        Enrollment.objects.filter(user=self.student).delete()

        response = self.client.get("/api/classes/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_logged_out_request_is_rejected(self):
        self.client.credentials()

        response = self.client.get("/api/classes/")

        self.assertEqual(response.status_code, 401)

    def test_professor_request_is_rejected(self):
        self.login_as(self.professor)

        response = self.client.get("/api/classes/")

        self.assertEqual(response.status_code, 403)

    def test_duplicate_enrollment_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Enrollment.objects.create(
                    user=self.student,
                    classroom=self.classroom,
                )

    def test_counts_available_and_uncompleted_quizzes(self):
        yesterday = timezone.now() - timedelta(days=1)

        completed = self.make_quiz(
            "Completed quiz", yesterday, question_count=3
        )
        new = self.make_quiz(
            "New quiz", yesterday, question_count=2
        )
        self.make_quiz("Draft quiz", None)
        self.make_quiz(
            "Future quiz",
            timezone.now() + timedelta(days=1),
        )
        self.make_quiz(
            "Lecture without questions",
            yesterday,
            question_count=0,
        )

        QuizCompletion.objects.create(
            user=self.student,
            lecture=completed,
        )
        QuizCompletion.objects.create(
            user=self.other_student,
            lecture=new,
        )

        response = self.client.get("/api/classes/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["quiz_count"], 2)
        self.assertEqual(response.data[0]["new_quiz_count"], 1)

        QuizCompletion.objects.create(
            user=self.student,
            lecture=new,
        )
        response = self.client.get("/api/classes/")

        self.assertEqual(response.data[0]["quiz_count"], 2)
        self.assertEqual(response.data[0]["new_quiz_count"], 0)

    def test_classroom_without_professor(self):
        self.classroom.professor = None
        self.classroom.save()

        response = self.client.get("/api/classes/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data[0]["professor"])