from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Profile
from quizzes.models import Answer, Attempt, DayStreak, Lecture, Question
from .models import Classroom, Enrollment


class ClassStatsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Software Engineering")
        cls.other_classroom = Classroom.objects.create(name="AI")
        cls.now = timezone.now()

        cls.old = cls.make_lecture(cls.classroom, "Scrum", days_ago=3)
        cls.mid = cls.make_lecture(cls.classroom, "Testing", days_ago=2)
        cls.new = cls.make_lecture(cls.classroom, "Design", days_ago=1)
        cls.other_lecture = cls.make_lecture(
            cls.other_classroom, "Search", days_ago=1
        )

        cls.bharat = cls.make_user("bharat", "Bharat", "Kawar")
        cls.alex = cls.make_user("alex", "Alex", "Smith")
        cls.sam = cls.make_user("sam", "Sam", "Rivera")
        cls.professor = cls.make_user(
            "professor", "Pat", "Teacher", role="professor"
        )
        cls.outsider = cls.make_user("outsider", "Other", "Student")

        for user in (cls.bharat, cls.alex, cls.sam):
            Enrollment.objects.create(user=user, classroom=cls.classroom)

        cls.url = reverse("class-stats", kwargs={"pk": cls.classroom.pk})

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

    @classmethod
    def make_lecture(cls, classroom, title, days_ago=1, questions=3):
        lecture = Lecture.objects.create(
            classroom=classroom,
            title=title,
            published_at=cls.now - timedelta(days=days_ago),
        )
        for position in range(questions):
            Question.objects.create(
                lecture=lecture,
                prompt=f"{title} question {position}",
                choices=["a", "b", "c", "d"],
                correct_index=0,
                difficulty="easy",
                position=position,
            )
        return lecture

    def setUp(self):
        self.client.force_authenticate(user=self.bharat)

    def add_attempt(
        self, user, points, lecture=None, correct=0, completed=True
    ):
        lecture = lecture or self.old
        attempt = Attempt.objects.create(
            user=user,
            lecture=lecture,
            total_points=points,
            completed_at=timezone.now() if completed else None,
        )
        for index, question in enumerate(lecture.questions.all()):
            Answer.objects.create(
                attempt=attempt,
                question=question,
                chosen_index=0,
                is_correct=index < correct,
                time_taken_ms=1000,
            )
        return attempt

    def get_stats(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.data

    def lecture_item(self, data, lecture):
        return next(
            item for item in data["lectures"] if item["id"] == lecture.id
        )

    def test_response_names_class_by_id_and_name(self):
        data = self.get_stats()

        self.assertEqual(data["classroom_id"], self.classroom.pk)
        self.assertEqual(data["classroom"], "Software Engineering")

    def test_student_with_no_attempts_gets_zeros(self):
        data = self.get_stats()

        self.assertEqual(data["total_points"], 0)
        self.assertEqual(data["quizzes_played"], 0)
        self.assertEqual(data["quizzes_total"], 3)
        self.assertEqual(data["rank"], 1)
        self.assertEqual(data["points_to_next_rank"], 0)
        self.assertEqual(len(data["lectures"]), 3)

        for item in data["lectures"]:
            self.assertEqual(item["best_score"], 0)
            self.assertEqual(item["correct_count"], 0)
            self.assertTrue(item["is_new"])
            self.assertEqual(item["question_count"], 3)

    def test_played_lecture_reports_best_attempt(self):
        self.add_attempt(self.bharat, 100, correct=1)
        self.add_attempt(self.bharat, 300, correct=3)

        data = self.get_stats()
        item = self.lecture_item(data, self.old)

        self.assertEqual(item["best_score"], 300)
        self.assertEqual(item["correct_count"], 3)
        self.assertFalse(item["is_new"])
        self.assertEqual(data["quizzes_played"], 1)
        self.assertEqual(data["total_points"], 400)

    def test_lower_repeat_attempt_does_not_lower_best_score(self):
        self.add_attempt(self.bharat, 300, correct=3)
        self.add_attempt(self.bharat, 100, correct=1)

        item = self.lecture_item(self.get_stats(), self.old)

        self.assertEqual(item["best_score"], 300)
        self.assertEqual(item["correct_count"], 3)

    def test_tied_attempts_use_the_lowest_attempt_id(self):
        self.add_attempt(self.bharat, 200, correct=2)
        self.add_attempt(self.bharat, 200, correct=3)

        item = self.lecture_item(self.get_stats(), self.old)

        self.assertEqual(item["best_score"], 200)
        self.assertEqual(item["correct_count"], 2)

    def test_incomplete_attempt_is_not_played(self):
        self.add_attempt(self.bharat, 500, correct=3, completed=False)

        data = self.get_stats()
        item = self.lecture_item(data, self.old)

        self.assertEqual(data["quizzes_played"], 0)
        self.assertEqual(data["total_points"], 0)
        self.assertTrue(item["is_new"])
        self.assertEqual(item["best_score"], 0)

    def test_lectures_are_newest_first(self):
        data = self.get_stats()

        self.assertEqual(
            [item["id"] for item in data["lectures"]],
            [self.new.id, self.mid.id, self.old.id],
        )

    def test_up_next_is_first_unplayed_lecture_newest_first(self):
        self.add_attempt(self.bharat, 100, lecture=self.new, correct=1)

        data = self.get_stats()

        self.assertEqual(data["up_next"]["id"], self.mid.id)
        self.assertEqual(
            data["up_next"], self.lecture_item(data, self.mid)
        )

    def test_up_next_is_null_when_everything_is_played(self):
        for lecture in (self.old, self.mid, self.new):
            self.add_attempt(self.bharat, 100, lecture=lecture, correct=1)

        data = self.get_stats()

        self.assertIsNone(data["up_next"])
        self.assertEqual(data["quizzes_played"], 3)

    def test_rank_and_points_to_next_rank(self):
        self.add_attempt(self.alex, 500)
        self.add_attempt(self.bharat, 300)
        self.add_attempt(self.sam, 300)

        data = self.get_stats()
        self.assertEqual(data["rank"], 2)
        self.assertEqual(data["total_points"], 300)
        self.assertEqual(data["points_to_next_rank"], 200)

        self.client.force_authenticate(user=self.alex)
        data = self.get_stats()
        self.assertEqual(data["rank"], 1)
        self.assertEqual(data["points_to_next_rank"], 0)

    def test_points_to_next_rank_uses_nearest_of_several_scores_above(self):
        dana = self.make_user("dana", "Dana", "Lee")
        Enrollment.objects.create(user=dana, classroom=self.classroom)
        self.add_attempt(self.alex, 600)
        self.add_attempt(self.sam, 500)
        self.add_attempt(dana, 400)
        self.add_attempt(self.bharat, 300)

        data = self.get_stats()
        self.assertEqual(data["rank"], 4)
        self.assertEqual(data["points_to_next_rank"], 100)

        self.client.force_authenticate(user=self.sam)
        data = self.get_stats()
        self.assertEqual(data["rank"], 2)
        self.assertEqual(data["points_to_next_rank"], 100)

    def test_zero_attempt_student_shares_last_rank_behind_scorers(self):
        self.add_attempt(self.alex, 300)
        self.add_attempt(self.sam, 100)

        data = self.get_stats()

        self.assertEqual(data["total_points"], 0)
        self.assertEqual(data["rank"], 3)
        self.assertEqual(data["points_to_next_rank"], 100)
        self.assertEqual(data["quizzes_played"], 0)
        self.assertIsNotNone(data["up_next"])

    def test_other_class_attempts_are_excluded(self):
        self.add_attempt(self.bharat, 900, lecture=self.other_lecture)

        data = self.get_stats()

        self.assertEqual(data["total_points"], 0)
        self.assertEqual(data["quizzes_played"], 0)
        for item in data["lectures"]:
            self.assertEqual(item["best_score"], 0)

    def test_unavailable_lectures_are_excluded(self):
        draft = self.make_lecture(self.classroom, "Draft")
        draft.published_at = None
        draft.save()
        future = self.make_lecture(self.classroom, "Future", days_ago=-2)
        empty = self.make_lecture(self.classroom, "Empty", questions=0)

        data = self.get_stats()
        ids = [item["id"] for item in data["lectures"]]

        for lecture in (draft, future, empty):
            self.assertNotIn(lecture.id, ids)
        self.assertEqual(data["quizzes_total"], 3)

    def test_student_with_no_streak_data_gets_zeros(self):
        data = self.get_stats()

        self.assertEqual(data["day_streak"], 0)
        self.assertEqual(data["answer_streak"], 0)

    @patch("classrooms.stats.timezone.localdate")
    def test_day_streak_is_returned(self, localdate):
        localdate.return_value = date(2026, 11, 11)
        DayStreak.objects.create(
            user=self.bharat, count=3, last_day=date(2026, 11, 10)
        )

        self.assertEqual(self.get_stats()["day_streak"], 3)

    @patch("classrooms.stats.timezone.localdate")
    def test_day_streak_reads_zero_after_a_missed_day(self, localdate):
        localdate.return_value = date(2026, 11, 11)
        DayStreak.objects.create(
            user=self.bharat, count=3, last_day=date(2026, 11, 9)
        )

        self.assertEqual(self.get_stats()["day_streak"], 0)

    def test_answer_streak_comes_from_newest_attempt_in_this_class(self):
        older = self.add_attempt(self.bharat, 100)
        older.answer_streak = 5
        older.save()
        newer = self.add_attempt(self.bharat, 100, completed=False)
        newer.answer_streak = 2
        newer.save()
        elsewhere = self.add_attempt(
            self.bharat, 100, lecture=self.other_lecture
        )
        elsewhere.answer_streak = 9
        elsewhere.save()

        self.assertEqual(self.get_stats()["answer_streak"], 2)

    @patch("classrooms.stats.timezone.localdate")
    def test_streaks_are_per_student(self, localdate):
        localdate.return_value = date(2026, 11, 11)
        DayStreak.objects.create(
            user=self.alex, count=4, last_day=date(2026, 11, 11)
        )
        attempt = self.add_attempt(self.alex, 100)
        attempt.answer_streak = 7
        attempt.save()

        data = self.get_stats()

        self.assertEqual(data["day_streak"], 0)
        self.assertEqual(data["answer_streak"], 0)

    def test_requires_login(self):
        self.client.force_authenticate(user=None)

        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_professor_gets_403(self):
        self.client.force_authenticate(user=self.professor)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_unenrolled_student_gets_403(self):
        self.client.force_authenticate(user=self.outsider)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_unknown_class_gets_404(self):
        self.client.force_authenticate(user=self.outsider)
        url = reverse("class-stats", kwargs={"pk": 999999})

        self.assertEqual(self.client.get(url).status_code, 404)

    def test_query_count_does_not_grow_with_lectures(self):
        def attempt_on_every_lecture():
            for lecture in self.classroom.lectures.all():
                self.add_attempt(
                    self.bharat, 100, lecture=lecture, correct=1
                )

        attempt_on_every_lecture()
        with self.assertNumQueries(7):
            self.assertEqual(
                len(self.client.get(self.url).data["lectures"]), 3
            )

        for index in range(2):
            self.make_lecture(self.classroom, f"Extra {index}", days_ago=5)
        attempt_on_every_lecture()
        with self.assertNumQueries(7):
            self.assertEqual(
                len(self.client.get(self.url).data["lectures"]), 5
            )
