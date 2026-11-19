
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from accounts.models import Profile
from classrooms.models import Classroom, Enrollment
from quizzes.models import Answer, Attempt, Lecture, Question


class ProfessorClassLecturesTests(APITestCase):
    def setUp(self):
        self.professor = User.objects.create_user(
            username="professor",
            password="testpass",
        )
        Profile.objects.create(
            user=self.professor,
            role="professor",
        )

        self.other_professor = User.objects.create_user(
            username="other_professor",
            password="testpass",
        )
        Profile.objects.create(
            user=self.other_professor,
            role="professor",
        )

        self.student = User.objects.create_user(
            username="student",
            password="testpass",
        )
        Profile.objects.create(
            user=self.student,
            role="student",
        )

        self.classroom = Classroom.objects.create(
            name="Software Engineering",
            professor=self.professor,
        )

        self.url = reverse(
            "professor-class-lectures",
            args=[self.classroom.id],
        )

    def test_professor_can_view_lectures(self):
        published = Lecture.objects.create(
            classroom=self.classroom,
            title="Published Lecture",
            published_at=timezone.now(),
        )
        draft = Lecture.objects.create(
            classroom=self.classroom,
            title="Draft Lecture",
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        lectures = {
            item["id"]: item for item in response.data
        }

        self.assertEqual(
            lectures[published.id]["status"],
            "published",
        )
        self.assertEqual(
            lectures[draft.id]["status"],
            "pending",
        )
        self.assertEqual(
            lectures[draft.id]["title"],
            "Draft Lecture",
        )

    def test_empty_class_returns_empty_list(self):
        self.client.force_authenticate(user=self.professor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_other_professor_forbidden(self):
        self.client.force_authenticate(
            user=self.other_professor
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_student_forbidden(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unknown_class_returns_404(self):
        self.client.force_authenticate(user=self.professor)

        response = self.client.get(
            reverse("professor-class-lectures", args=[999999])
        )

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get(self.url)

        self.assertIn(response.status_code, [401, 403])

    def test_does_not_include_other_class_lectures(self):
        other_class = Classroom.objects.create(
            name="Artificial Intelligence",
            professor=self.professor,
        )
        Lecture.objects.create(
            classroom=other_class,
            title="Other Class Lecture",
        )
        Lecture.objects.create(
            classroom=self.classroom,
            title="Correct Lecture",
        )

        self.client.force_authenticate(user=self.professor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["title"],
            "Correct Lecture",
        )

    def test_lecture_row_includes_upload_date_questions_played_and_average(self):
        lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Week 1",
            published_at=timezone.now(),
        )
        first = Question.objects.create(
            lecture=lecture,
            prompt="What is 2 + 2?",
            choices=["4", "3", "5", "6"],
            correct_index=0,
            difficulty="easy",
            position=1,
        )
        Question.objects.create(
            lecture=lecture,
            prompt="What is 3 + 3?",
            choices=["6", "5", "7", "8"],
            correct_index=0,
            difficulty="medium",
            position=2,
        )
        student = User.objects.create_user(
            username="enrolled",
            password="testpass",
        )
        Profile.objects.create(user=student, role="student")
        Enrollment.objects.create(user=student, classroom=self.classroom)
        other = User.objects.create_user(
            username="also",
            password="testpass",
        )
        Profile.objects.create(user=other, role="student")
        Enrollment.objects.create(user=other, classroom=self.classroom)

        low = Attempt.objects.create(
            user=student,
            lecture=lecture,
            total_points=0,
            completed_at=timezone.now(),
        )
        Answer.objects.create(
            attempt=low,
            question=first,
            chosen_index=1,
            is_correct=False,
            time_taken_ms=1000,
            points_awarded=0,
        )
        Attempt.objects.create(
            user=student,
            lecture=lecture,
            total_points=300,
            completed_at=timezone.now(),
        )
        Attempt.objects.create(
            user=other,
            lecture=lecture,
            total_points=100,
            completed_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)
        row = response.data[0]

        self.assertEqual(row["question_count"], 2)
        self.assertEqual(row["students_played"], 2)
        self.assertEqual(row["class_average"], 200)
        uploaded_at = row["uploaded_at"]
        if isinstance(uploaded_at, str):
            uploaded_at = parse_datetime(uploaded_at)
        self.assertEqual(uploaded_at, lecture.created_at)

    def test_a_finished_quiz_with_zero_points_still_counts(self):
        lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Quiet week",
            published_at=timezone.now(),
        )
        student = User.objects.create_user(
            username="quiet",
            password="testpass",
        )
        Profile.objects.create(user=student, role="student")
        Enrollment.objects.create(user=student, classroom=self.classroom)
        Attempt.objects.create(
            user=student,
            lecture=lecture,
            total_points=0,
            completed_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.data[0]["students_played"], 1)
        self.assertEqual(response.data[0]["class_average"], 0)

    def test_lecture_average_is_null_when_nobody_has_played(self):
        Lecture.objects.create(
            classroom=self.classroom,
            title="Unused",
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.data[0]["students_played"], 0)
        self.assertIsNone(response.data[0]["class_average"])
        self.assertEqual(response.data[0]["question_count"], 0)
        self.assertIn("uploaded_at", response.data[0])
