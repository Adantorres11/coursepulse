from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Profile
from classrooms.models import Classroom


class ClassCreateTests(APITestCase):
    def setUp(self):
        self.professor = User.objects.create_user(
            username="professor",
            password="testpass",
        )
        Profile.objects.create(
            user=self.professor,
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

        self.url = reverse("student-class-list")

    def test_professor_can_create_class(self):
        self.client.force_authenticate(user=self.professor)

        response = self.client.post(
            self.url,
            {"name": "Software Engineering"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        classroom = Classroom.objects.get(
            id=response.data["id"]
        )

        self.assertEqual(classroom.name, "Software Engineering")
        self.assertEqual(classroom.professor, self.professor)
        self.assertEqual(
            response.data["access_code"],
            classroom.access_code,
        )
        self.assertRegex(classroom.access_code, r"^[A-Z0-9]{6}$")

    def test_access_codes_are_unique(self):
        self.client.force_authenticate(user=self.professor)

        first = self.client.post(
            self.url,
            {"name": "Class One"},
            format="json",
        )

        second = self.client.post(
            self.url,
            {"name": "Class Two"},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(
            first.data["access_code"],
            second.data["access_code"],
        )

    def test_student_cannot_create_class(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.post(
            self.url,
            {"name": "Unauthorized Class"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Classroom.objects.count(), 0)

    def test_missing_name(self):
        self.client.force_authenticate(user=self.professor)

        response = self.client.post(
            self.url,
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_blank_name(self):
        self.client.force_authenticate(user=self.professor)

        response = self.client.post(
            self.url,
            {"name": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_user(self):
        response = self.client.post(
            self.url,
            {"name": "Test Class"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)