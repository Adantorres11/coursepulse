from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase

from accounts.models import Profile
from classrooms.models import Classroom, Enrollment


class ClassRosterTests(APITestCase):
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
            first_name="John",
            last_name="Smith",
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
            "class-roster",
            args=[self.classroom.id],
        )

    def test_professor_can_view_roster(self):
        enrollment = Enrollment.objects.create(
            user=self.student,
            classroom=self.classroom,
        )

        second_student = User.objects.create_user(
            username="student2",
            password="testpass",
        )
        Profile.objects.create(
            user=second_student,
            role="student",
        )
        Enrollment.objects.create(
            user=second_student,
            classroom=self.classroom,
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["name"], "John Smith")
        self.assertEqual(response.data[1]["name"], "student2")

        self.assertEqual(
            parse_datetime(response.data[0]["joined_at"]),
            enrollment.joined_at,
        )

    def test_empty_roster(self):
        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_other_class_students_not_included(self):
        other_class = Classroom.objects.create(
            name="Artificial Intelligence",
            professor=self.professor,
        )
        Enrollment.objects.create(
            user=self.student,
            classroom=other_class,
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_other_professor_cannot_view_roster(self):
        self.client.force_authenticate(
            user=self.other_professor
        )
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_student_cannot_view_roster(self):
        Enrollment.objects.create(
            user=self.student,
            classroom=self.classroom,
        )

        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unknown_class(self):
        self.client.force_authenticate(user=self.professor)

        url = reverse(
            "class-roster",
            args=[self.classroom.id + 10000],
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)