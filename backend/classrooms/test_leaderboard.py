from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Profile
from quizzes.models import Attempt, Lecture
from .models import Classroom, Enrollment


class ClassLeaderboardTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Software Engineering")
        cls.other_classroom = Classroom.objects.create(name="AI")

        cls.lecture = Lecture.objects.create(
            classroom=cls.classroom,
            title="Scrum",
        )
        cls.second_lecture = Lecture.objects.create(
            classroom=cls.classroom,
            title="Testing",
        )
        cls.other_lecture = Lecture.objects.create(
            classroom=cls.other_classroom,
            title="Search",
        )

        cls.bharat = cls.make_user("bharat", "Bharat", "Kawar")
        cls.alex = cls.make_user("alex", "Alex", "Smith")
        cls.sam = cls.make_user("sam", "Sam", "Rivera")
        cls.zero = cls.make_user("zero", "Zero", "Points")
        cls.outsider = cls.make_user("outsider", "Other", "Student")
        cls.professor = cls.make_user(
            "professor", "Pat", "Teacher", role="professor"
        )

        for user in (cls.bharat, cls.alex, cls.sam, cls.zero):
            Enrollment.objects.create(user=user, classroom=cls.classroom)

        cls.url = reverse(
            "class-leaderboard",
            kwargs={"pk": cls.classroom.pk},
        )

    @classmethod
    def make_user(cls, username, first_name, last_name, role="student"):
        user = get_user_model().objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        Profile.objects.update_or_create(
            user=user,
            defaults={"role": role},
        )
        return user

    def setUp(self):
        self.client.force_authenticate(user=self.bharat)

    def add_attempt(self, user, points, lecture=None, completed=True):
        return Attempt.objects.create(
            user=user,
            lecture=lecture or self.lecture,
            total_points=points,
            completed_at=timezone.now() if completed else None,
        )

    def test_points_sum_across_lectures_and_repeat_attempts(self):
        self.add_attempt(self.bharat, 100)
        self.add_attempt(self.bharat, 100)
        self.add_attempt(self.bharat, 200, lecture=self.second_lecture)
        self.add_attempt(self.alex, 300)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0], {
            "rank": 1,
            "display_name": "Bharat K.",
            "points": 400,
            "is_current_user": True,
        })
        self.assertEqual(response.data[1]["points"], 300)
        self.assertEqual(response.data[1]["rank"], 2)
        self.assertEqual(len(response.data), 4)

    def test_ties_share_competition_rank(self):
        self.add_attempt(self.bharat, 500)
        self.add_attempt(self.alex, 500)
        self.add_attempt(self.sam, 100)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [entry["rank"] for entry in response.data],
            [1, 1, 3, 4],
        )
        self.assertEqual(
            [entry["display_name"] for entry in response.data[:2]],
            ["Bharat K.", "Alex S."],
        )

    def test_zero_point_students_are_last_and_tied(self):
        self.add_attempt(self.alex, 100)
        self.add_attempt(self.sam, 0)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [entry["points"] for entry in response.data],
            [100, 0, 0, 0],
        )
        self.assertEqual(
            [entry["rank"] for entry in response.data],
            [1, 2, 2, 2],
        )

    def test_only_current_user_is_flagged(self):
        self.client.force_authenticate(user=self.alex)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        flagged = [
            entry for entry in response.data
            if entry["is_current_user"]
        ]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["display_name"], "Alex S.")

    def test_other_classes_and_incomplete_attempts_are_excluded(self):
        self.add_attempt(self.bharat, 100)
        self.add_attempt(self.bharat, 900, lecture=self.other_lecture)
        self.add_attempt(self.bharat, 800, completed=False)

        # Membership in another class must not duplicate this class's points.
        Enrollment.objects.create(
            user=self.bharat,
            classroom=self.other_classroom,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        current_entry = next(
            entry for entry in response.data
            if entry["is_current_user"]
        )
        self.assertEqual(current_entry["points"], 100)

    def test_unenrolled_users_and_professors_are_not_listed(self):
        self.add_attempt(self.outsider, 1000)
        Enrollment.objects.create(
            user=self.professor,
            classroom=self.classroom,
        )
        self.add_attempt(self.professor, 2000)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {entry["display_name"] for entry in response.data},
            {"Bharat K.", "Alex S.", "Sam R.", "Zero P."},
        )

    def test_name_fallbacks(self):
        self.bharat.last_name = ""
        self.bharat.save(update_fields=["last_name"])
        self.alex.first_name = ""
        self.alex.save(update_fields=["first_name"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["display_name"], "Bharat")
        self.assertEqual(response.data[1]["display_name"], "Student")

    def test_unenrolled_student_gets_403(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_professor_gets_403_even_when_enrolled(self):
        Enrollment.objects.create(
            user=self.professor,
            classroom=self.classroom,
        )
        self.client.force_authenticate(user=self.professor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_user_without_profile_gets_403(self):
        Profile.objects.filter(user=self.bharat).delete()

        fresh_user = get_user_model().objects.get(pk=self.bharat.pk)
        self.client.force_authenticate(user=fresh_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unknown_class_gets_404(self):
        missing_id = self.other_classroom.pk + 1000
        url = reverse("class-leaderboard", kwargs={"pk": missing_id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_unknown_class_gets_404_for_unenrolled_student(self):
        self.client.force_authenticate(user=self.outsider)
        missing_id = self.other_classroom.pk + 1000
        url = reverse("class-leaderboard", kwargs={"pk": missing_id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_missing_token_gets_401(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_invalid_token_gets_401(self):
        self.client.force_authenticate(user=None)
        self.client.credentials(
            HTTP_AUTHORIZATION="Token invalid-token",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)