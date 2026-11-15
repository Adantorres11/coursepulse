from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import DayStreak


class DayStreakAdminTests(TestCase):
    def test_day_streak_is_registered(self):
        self.assertTrue(admin.site.is_registered(DayStreak))

    def test_day_streak_list_page_loads(self):
        superuser = get_user_model().objects.create_superuser(
            "admin", "a@example.com", "pw"
        )
        student = get_user_model().objects.create_user("student")
        DayStreak.objects.create(user=student, count=3, last_day=date(2026, 11, 12))
        self.client.force_login(superuser)
        response = self.client.get(reverse("admin:quizzes_daystreak_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "student")
