from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Profile
from classrooms.models import Classroom, Enrollment
from quizzes.models import Lecture


class ProfessorClassListTests(APITestCase):
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

        self.url = reverse("professor-class-list")

    def test_professor_sees_own_classes_only(self):
        Classroom.objects.create(
            name="Other Class",
            professor=self.other_professor,
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["id"],
            self.classroom.id,
        )
        self.assertEqual(
            response.data[0]["name"],
            self.classroom.name,
        )
        self.assertEqual(
            response.data[0]["access_code"],
            self.classroom.access_code,
        )

    def test_student_and_lecture_counts(self):
        second_student = User.objects.create_user(
            username="student2",
            password="testpass",
        )
        Profile.objects.create(
            user=second_student,
            role="student",
        )

        Enrollment.objects.create(
            user=self.student,
            classroom=self.classroom,
        )
        Enrollment.objects.create(
            user=second_student,
            classroom=self.classroom,
        )

        for number in range(3):
            Lecture.objects.create(
                classroom=self.classroom,
                title=f"Lecture {number + 1}",
            )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data[0]["student_count"], 2
        )
        self.assertEqual(
            response.data[0]["lecture_count"], 3
        )

    def test_empty_class_counts(self):
        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data[0]["student_count"], 0
        )
        self.assertEqual(
            response.data[0]["lecture_count"], 0
        )

    def test_professor_with_no_classes(self):
        self.client.force_authenticate(
            user=self.other_professor
        )
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_student_cannot_access(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)