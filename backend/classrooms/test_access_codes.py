from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Profile
from classrooms.models import Classroom, Enrollment
from quizzes.models import Lecture, Question

User = get_user_model()


class ClassAccessCodeTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="Maple!River82",
        )
        Profile.objects.create(
            user=self.student,
            role="student",
        )

        self.professor = User.objects.create_user(
            username="professor@example.com",
            first_name="Alex",
            last_name="Smith",
        )
        Profile.objects.create(
            user=self.professor,
            role="professor",
        )

        self.classroom = Classroom.objects.create(
            name="Software Engineering",
            course_code="CS 3398",
            professor=self.professor,
            access_code="ABC123",
        )

        lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Scrum",
            published_at=timezone.now(),
        )
        Question.objects.create(
            lecture=lecture,
            prompt="What is a sprint?",
            choices=["A", "B", "C", "D"],
            correct_index=0,
            difficulty="easy",
        )

        token = Token.objects.create(user=self.student)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

    def test_lookup_valid_code(self):
        response = self.client.get(
            "/api/classes/lookup/",
            {"code": "ABC123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Software Engineering")
        self.assertEqual(response.data["course_code"], "CS 3398")
        self.assertEqual(
            response.data["professor"]["name"], "Alex Smith"
        )
        self.assertEqual(response.data["quiz_count"], 1)
        self.assertFalse(Enrollment.objects.exists())

    def test_lookup_is_case_insensitive(self):
        response = self.client.get(
            "/api/classes/lookup/",
            {"code": "abc123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.classroom.id)

    def test_unknown_code_returns_404(self):
        lookup = self.client.get(
            "/api/classes/lookup/",
            {"code": "ZZZ999"},
        )
        join = self.client.post(
            "/api/classes/join/",
            {"code": "ZZZ999"},
            format="json",
        )

        for response in [lookup, join]:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(
                response.data["detail"],
                "We couldn't find a class with that code",
            )

        self.assertFalse(Enrollment.objects.exists())

    def test_join_with_lowercase_code(self):
        response = self.client.post(
            "/api/classes/join/",
            {"code": "abc123"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["id"], self.classroom.id)
        self.assertEqual(response.data["quiz_count"], 1)
        self.assertTrue(
            Enrollment.objects.filter(
                user=self.student,
                classroom=self.classroom,
            ).exists()
        )

        classes = self.client.get("/api/classes/")
        self.assertEqual(classes.status_code, 200)
        self.assertEqual(
            [item["id"] for item in classes.data],
            [self.classroom.id],
        )

    def test_repeat_join_does_not_duplicate_enrollment(self):
        first = self.client.post(
            "/api/classes/join/",
            {"code": "ABC123"},
            format="json",
        )
        second = self.client.post(
            "/api/classes/join/",
            {"code": "abc123"},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            Enrollment.objects.filter(
                user=self.student,
                classroom=self.classroom,
            ).count(),
            1,
        )

    def test_endpoints_require_login(self):
        self.client.credentials()

        lookup = self.client.get(
            "/api/classes/lookup/",
            {"code": "ABC123"},
        )
        join = self.client.post(
            "/api/classes/join/",
            {"code": "ABC123"},
            format="json",
        )

        self.assertEqual(lookup.status_code, 401)
        self.assertEqual(join.status_code, 401)
        self.assertFalse(Enrollment.objects.exists())

    def test_professor_cannot_join_or_lookup(self):
        token = Token.objects.create(user=self.professor)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

        lookup = self.client.get(
            "/api/classes/lookup/",
            {"code": "ABC123"},
        )
        join = self.client.post(
            "/api/classes/join/",
            {"code": "ABC123"},
            format="json",
        )

        self.assertEqual(lookup.status_code, 403)
        self.assertEqual(join.status_code, 403)
        self.assertFalse(Enrollment.objects.exists())

    def test_malformed_codes_are_rejected(self):
        for data in [{}, {"code": "ABC"}, {"code": "ABC!23"}]:
            with self.subTest(data=data):
                lookup = self.client.get(
                    "/api/classes/lookup/", data
                )
                join = self.client.post(
                    "/api/classes/join/", data, format="json"
                )

                self.assertEqual(lookup.status_code, 400)
                self.assertEqual(join.status_code, 400)

    def test_generated_codes_have_expected_format(self):
        first = Classroom.objects.create(name="First")
        second = Classroom.objects.create(name="Second")

        self.assertRegex(first.access_code, r"^[A-Z0-9]{6}$")
        self.assertRegex(second.access_code, r"^[A-Z0-9]{6}$")
        self.assertNotEqual(first.access_code, second.access_code)

    def test_duplicate_access_code_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Classroom.objects.create(
                    name="Duplicate",
                    access_code="ABC123",
                )