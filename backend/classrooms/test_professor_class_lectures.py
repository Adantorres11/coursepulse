
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Profile
from classrooms.models import Classroom
from quizzes.models import Lecture


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
