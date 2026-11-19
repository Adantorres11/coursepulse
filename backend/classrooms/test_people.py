from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.exceptions import FieldDoesNotExist
from django.test import SimpleTestCase

from classrooms.people import person_display_name


class _UsernameMeta:
    def get_field(self, name):
        if name != "username":
            raise FieldDoesNotExist(name)


class _NoUsernameMeta:
    def get_field(self, name):
        raise FieldDoesNotExist(name)


def _person(profile):
    return SimpleNamespace(
        username="ada@school.edu",
        profile=profile,
        _meta=_NoUsernameMeta(),
        get_full_name=lambda: "Ada Lovelace",
    )


class PersonDisplayNameTests(SimpleTestCase):
    def test_full_name_beats_the_login(self):
        user = User(
            username="ada@school.edu",
            first_name="Ada",
            last_name="Lovelace",
        )

        self.assertEqual(person_display_name(user), "Ada Lovelace")

    def test_login_is_the_fallback(self):
        user = User(username="ada@school.edu")

        self.assertEqual(person_display_name(user), "ada@school.edu")

    def test_profile_username_is_used_when_that_field_exists(self):
        profile = SimpleNamespace(username="ada", _meta=_UsernameMeta())

        self.assertEqual(person_display_name(_person(profile)), "ada")

    def test_blank_profile_username_falls_back_to_the_full_name(self):
        profile = SimpleNamespace(username="  ", _meta=_UsernameMeta())

        self.assertEqual(person_display_name(_person(profile)), "Ada Lovelace")

    def test_stray_username_attribute_is_ignored_without_the_field(self):
        profile = SimpleNamespace(username="ada", _meta=_NoUsernameMeta())

        self.assertEqual(person_display_name(_person(profile)), "Ada Lovelace")
