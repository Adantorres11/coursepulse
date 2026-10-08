from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Profile

User = get_user_model()


class AuthTests(APITestCase):
    def registration_data(self, **changes):
        data = {
            "email": "student@example.com",
            "password": "Maple!River82",
            "role": "student",
        }
        data.update(changes)
        return data

    def create_account(self):
        user = User.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="Maple!River82",
        )
        Profile.objects.create(user=user, role="student")
        return user

    def test_register_student(self):
        response = self.client.post(
            "/api/auth/register/",
            self.registration_data(),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="student@example.com")
        self.assertEqual(user.profile.role, "student")
        self.assertTrue(user.check_password("Maple!River82"))
        self.assertNotEqual(user.password, "Maple!River82")
        self.assertEqual(
            response.data["token"],
            Token.objects.get(user=user).key,
        )
        self.assertNotIn("password", response.data["user"])

    def test_register_professor(self):
        response = self.client.post(
            "/api/auth/register/",
            self.registration_data(role="professor"),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            User.objects.get(email="student@example.com").profile.role,
            "professor",
        )

    def test_duplicate_email_rejected(self):
        self.create_account()
        response = self.client.post(
            "/api/auth/register/",
            self.registration_data(email="STUDENT@example.com"),
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)
        self.assertEqual(User.objects.count(), 1)

    def test_weak_passwords_rejected(self):
        for password in ["abc", "password", "123456789"]:
            with self.subTest(password=password):
                response = self.client.post(
                    "/api/auth/register/",
                    self.registration_data(password=password),
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("password", response.data)

        self.assertEqual(User.objects.count(), 0)

    def test_invalid_registration_fields(self):
        cases = [
            self.registration_data(email="not-an-email"),
            self.registration_data(role="admin"),
            {"email": "student@example.com", "role": "student"},
        ]

        for data in cases:
            with self.subTest(data=data):
                response = self.client.post(
                    "/api/auth/register/", data, format="json"
                )
                self.assertEqual(response.status_code, 400)

        self.assertEqual(User.objects.count(), 0)

    def test_valid_login(self):
        user = self.create_account()
        response = self.client.post(
            "/api/auth/login/",
            {
                "email": "STUDENT@example.com",
                "password": "Maple!River82",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["token"],
            Token.objects.get(user=user).key,
        )

    def test_invalid_login(self):
        self.create_account()

        for email, password in [
            ("student@example.com", "wrong-password"),
            ("unknown@example.com", "Maple!River82"),
        ]:
            with self.subTest(email=email):
                response = self.client.post(
                    "/api/auth/login/",
                    {"email": email, "password": password},
                    format="json",
                )

                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.data["detail"],
                    "Invalid email or password.",
                )

    def test_missing_login_fields(self):
        response = self.client.post(
            "/api/auth/login/", {}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_me_requires_token(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_me_rejects_invalid_token(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token invalid-token"
        )

        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_me_with_valid_token(self):
        user = self.create_account()
        token = Token.objects.create(user=user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], user.email)
        self.assertEqual(response.data["role"], "student")