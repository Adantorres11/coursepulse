from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.usernames import assign_default_usernames, display_username

User = get_user_model()


class DefaultUsernameTests(TestCase):
    def test_email_usernames_become_unique_local_parts(self):
        first = User.objects.create_user(
            username="torres11@gmail.com",
            email="torres11@gmail.com",
            password="Maple!River82",
        )
        second = User.objects.create_user(
            username="torres11@school.edu",
            email="torres11@school.edu",
            password="Maple!River82",
        )
        dotted = User.objects.create_user(
            username="first.last+tag@school.edu",
            email="first.last+tag@school.edu",
            password="Maple!River82",
        )
        kept = User.objects.create_user(
            username="professor",
            email="professor@example.com",
            password="Maple!River82",
        )
        empty_local = User.objects.create_user(
            username="@@@",
            email="@@@",
            password="Maple!River82",
        )
        existing = User.objects.create_user(
            username="ada",
            email="ada-real@example.com",
            password="Maple!River82",
        )
        colliding = User.objects.create_user(
            username="ada@school.edu",
            email="ada@school.edu",
            password="Maple!River82",
        )

        assign_default_usernames(User)

        first.refresh_from_db()
        second.refresh_from_db()
        dotted.refresh_from_db()
        kept.refresh_from_db()
        empty_local.refresh_from_db()
        existing.refresh_from_db()
        colliding.refresh_from_db()

        self.assertEqual(first.username, "torres11")
        self.assertEqual(first.email, "torres11@gmail.com")
        self.assertEqual(second.username, "torres11_2")
        self.assertEqual(dotted.username, "firstlasttag")
        self.assertEqual(kept.username, "professor")
        self.assertEqual(kept.email, "professor@example.com")
        self.assertEqual(empty_local.username, "user")
        self.assertEqual(existing.username, "ada")
        self.assertEqual(colliding.username, "ada_2")

    def test_display_username_never_returns_an_email(self):
        legacy = User.objects.create_user(
            username="torres11@gmail.com",
            email="torres11@gmail.com",
            password="Maple!River82",
        )
        chosen = User.objects.create_user(
            username="ada",
            email="ada@school.edu",
            password="Maple!River82",
        )

        self.assertEqual(display_username(legacy), "torres11")
        self.assertEqual(display_username(chosen), "ada")
        self.assertEqual(display_username(None), "")
        self.assertNotIn("@", display_username(legacy))

    def test_migration_assigns_default_usernames(self):
        from importlib import import_module

        user = User.objects.create_user(
            username="ada@school.edu",
            email="ada@school.edu",
            password="Maple!River82",
        )
        migration = import_module(
            "accounts.migrations.0002_assign_default_usernames"
        )

        migration.forwards(apps, None)

        user.refresh_from_db()
        self.assertEqual(user.username, "ada")
        self.assertEqual(user.email, "ada@school.edu")
