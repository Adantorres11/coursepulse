from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from classrooms.models import Classroom
from classrooms.stats import build_class_stats, class_standings
from .models import Answer, Attempt, Lecture
from .parts import part_sizes
from .test_lectures import add_questions
from .testing import make_student


class PartSizeTests(SimpleTestCase):
    def test_small_lectures_stay_one_part(self):
        self.assertEqual(part_sizes(0), [])
        self.assertEqual(part_sizes(1), [1])
        self.assertEqual(part_sizes(5), [5])
        self.assertEqual(part_sizes(13), [13])

    def test_splits_are_even_and_have_no_tiny_tail(self):
        self.assertEqual(part_sizes(14), [7, 7])
        self.assertEqual(part_sizes(15), [8, 7])
        self.assertEqual(part_sizes(26), [13, 13])
        self.assertEqual(part_sizes(27), [9, 9, 9])
        self.assertEqual(part_sizes(30), [10, 10, 10])
        self.assertEqual(part_sizes(40), [10, 10, 10, 10])

    def test_every_part_stays_within_the_max_and_covers_every_question(self):
        for count in range(1, 80):
            sizes = part_sizes(count)
            self.assertEqual(sum(sizes), count)
            self.assertTrue(all(1 <= size <= 13 for size in sizes))
            self.assertLessEqual(max(sizes) - min(sizes), 1)


class PartPlayTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Software Engineering")
        cls.lecture = Lecture.objects.create(
            classroom=cls.classroom,
            title="Lecture 5",
            published_at=timezone.now() - timedelta(days=1),
        )
        add_questions(cls.lecture, 30)
        cls.questions = list(cls.lecture.questions.order_by("position", "id"))
        for question in cls.questions:
            question.choices = ["Alpha", "Bravo", "Charlie", "Delta"]
            question.correct_index = 0
            question.save()
        cls.student = make_student("ada", cls.classroom)
        cls.student.first_name = "Ada"
        cls.student.last_name = "Lovelace"
        cls.student.save()
        cls.other = make_student("grace", cls.classroom)
        cls.other.first_name = "Grace"
        cls.other.last_name = "Hopper"
        cls.other.save()

    def setUp(self):
        self.client.force_authenticate(self.student)

    def quiz(self, part, lecture=None):
        lecture = lecture or self.lecture
        return self.client.get(
            f"/api/lectures/{lecture.id}/quiz/?part={part}"
        )

    def start(self, question, part):
        return self.client.post(
            f"/api/lectures/{self.lecture.id}/questions/{question.id}/start/"
            f"?part={part}"
        )

    def answer(self, question, chosen_index, part):
        self.start(question, part)
        return self.client.post(
            f"/api/lectures/{self.lecture.id}/answers/",
            {
                "question_id": question.id,
                "chosen_index": chosen_index,
                "part": part,
            },
            format="json",
        )

    def test_thirty_questions_are_three_parts_of_the_same_questions(self):
        first = self.quiz(1)
        second = self.quiz(2)
        third = self.quiz(3)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["part_count"], 3)
        self.assertEqual(len(first.json()["questions"]), 10)
        self.assertEqual(len(second.json()["questions"]), 10)
        self.assertEqual(len(third.json()["questions"]), 10)
        self.assertEqual(
            {q["id"] for q in first.json()["questions"]},
            {q.id for q in self.questions[:10]},
        )
        self.assertEqual(
            {q["id"] for q in third.json()["questions"]},
            {q.id for q in self.questions[20:]},
        )
        self.assertNotIn("correct_index", first.content.decode())

        self.client.force_authenticate(self.other)
        other_first = self.quiz(1).json()
        self.assertEqual(
            {q["id"] for q in other_first["questions"]},
            {q["id"] for q in first.json()["questions"]},
        )

    def test_resume_keeps_the_saved_order(self):
        self.quiz(1)
        attempt = Attempt.objects.get(
            user=self.student, part_index=0, completed_at__isnull=True
        )
        part_ids = [question.id for question in self.questions[:10]]
        saved_order = list(reversed(part_ids))
        attempt.question_order = saved_order
        attempt.choice_orders = {
            str(question_id): [1, 2, 3, 0] for question_id in part_ids
        }
        attempt.save()

        def fail_if_called(_seq):
            raise AssertionError("resume shuffled again")

        with patch("quizzes.parts.random.shuffle", fail_if_called):
            again = self.quiz(1)

        body = again.json()
        self.assertEqual(
            [question["id"] for question in body["questions"]],
            saved_order,
        )
        self.assertEqual(
            body["questions"][0]["choices"],
            ["Bravo", "Charlie", "Delta", "Alpha"],
        )

    def test_each_student_keeps_their_own_order(self):
        self.quiz(1)
        self.client.force_authenticate(self.other)
        self.quiz(1)
        ada = Attempt.objects.get(user=self.student, part_index=0)
        grace = Attempt.objects.get(user=self.other, part_index=0)
        part_ids = [question.id for question in self.questions[:10]]
        ada.question_order = part_ids
        grace.question_order = list(reversed(part_ids))
        ada.save()
        grace.save()

        self.client.force_authenticate(self.student)
        ada_ids = [q["id"] for q in self.quiz(1).json()["questions"]]
        self.client.force_authenticate(self.other)
        grace_ids = [q["id"] for q in self.quiz(1).json()["questions"]]

        self.assertEqual(ada_ids, part_ids)
        self.assertEqual(grace_ids, list(reversed(part_ids)))
        self.assertEqual(self.quiz(1).json()["answered_question_ids"], [])

    def test_shuffled_choice_is_graded_against_the_real_correct_choice(self):
        question = self.questions[0]
        self.quiz(1)
        attempt = Attempt.objects.get(user=self.student, part_index=0)
        # Display order puts the real correct choice (original 0, "Alpha") last.
        orders = dict(attempt.choice_orders)
        orders[str(question.id)] = [1, 2, 3, 0]
        attempt.choice_orders = orders
        attempt.question_order = [question.id] + [
            q.id for q in self.questions[1:10]
        ]
        attempt.save()

        shown = self.quiz(1).json()["questions"][0]
        self.assertEqual(shown["choices"][3], "Alpha")

        # The old correct index is now a wrong button.
        wrong = self.answer(question, question.correct_index, part=1)
        self.assertEqual(wrong.status_code, 201)
        self.assertFalse(wrong.json()["is_correct"])
        self.assertEqual(wrong.json()["points_awarded"], 0)
        self.assertEqual(wrong.json()["correct_index"], 3)
        stored = Answer.objects.get(attempt=attempt, question=question)
        self.assertEqual(stored.chosen_index, 1)
        self.assertFalse(stored.is_correct)

    def test_pressing_the_shuffled_correct_button_scores_the_real_choice(self):
        question = self.questions[10]
        self.quiz(2)
        attempt = Attempt.objects.get(user=self.student, part_index=1)
        orders = dict(attempt.choice_orders)
        orders[str(question.id)] = [1, 2, 3, 0]
        attempt.choice_orders = orders
        attempt.question_order = [question.id] + [
            item.id for item in self.questions[11:20]
        ]
        attempt.save()

        response = self.answer(question, 3, part=2)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["is_correct"])
        self.assertEqual(response.json()["correct_index"], 3)
        self.assertEqual(response.json()["points_awarded"], 100)
        stored = Answer.objects.get(question=question)
        self.assertEqual(stored.chosen_index, 0)

    def test_out_of_part_question_is_rejected(self):
        self.quiz(1)
        outsider = self.questions[10]
        started = self.start(outsider, part=1)
        self.assertEqual(started.status_code, 404)
        response = self.client.post(
            f"/api/lectures/{self.lecture.id}/answers/",
            {
                "question_id": outsider.id,
                "chosen_index": 0,
                "part": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Answer.objects.exists())

    def test_tampered_choice_index_is_rejected(self):
        question = self.questions[0]
        self.quiz(1)
        self.start(question, part=1)
        response = self.client.post(
            f"/api/lectures/{self.lecture.id}/answers/",
            {"question_id": question.id, "chosen_index": 4, "part": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("chosen_index", response.json())
        self.assertFalse(Answer.objects.exists())

    def test_other_student_cannot_see_or_score_on_this_attempt(self):
        question = self.questions[0]
        self.quiz(1)
        attempt = Attempt.objects.get(user=self.student, part_index=0)
        attempt.choice_orders = {
            str(item.id): [0, 1, 2, 3] for item in self.questions[:10]
        }
        attempt.question_order = [q.id for q in self.questions[:10]]
        attempt.save()
        mine = self.answer(question, 0, part=1)
        self.assertTrue(mine.json()["is_correct"])
        my_points = Attempt.objects.get(user=self.student, part_index=0).total_points

        self.client.force_authenticate(self.other)
        their_quiz = self.quiz(1).json()
        self.assertEqual(their_quiz["answered_question_ids"], [])
        self.assertEqual(their_quiz["total_points"], 0)
        grace = Attempt.objects.get(
            user=self.other, part_index=0, completed_at__isnull=True
        )
        grace_orders = dict(grace.choice_orders)
        grace_orders[str(question.id)] = [0, 1, 2, 3]
        grace.choice_orders = grace_orders
        grace.save()
        their_answer = self.answer(question, 1, part=1)
        self.assertEqual(their_answer.status_code, 201)
        self.assertEqual(their_answer.json()["total_points"], 0)
        self.assertEqual(
            Attempt.objects.get(pk=attempt.pk).total_points,
            my_points,
        )
        review = self.client.get(
            f"/api/lectures/{self.lecture.id}/parts/1/review/"
        )
        self.assertEqual(review.status_code, 404)
        self.assertNotIn("Alpha", review.content.decode())

    def test_part_quiz_reports_points_for_questions_answered_earlier(self):
        question = self.questions[0]
        self.quiz(1)
        attempt = Attempt.objects.get(user=self.student, part_index=0)
        shown = attempt.choice_orders[str(question.id)].index(question.correct_index)
        response = self.answer(question, shown, part=1)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["is_correct"])
        body = self.quiz(1).json()
        self.assertEqual(
            body["answered_questions"],
            [
                {
                    "question_id": question.id,
                    "is_correct": True,
                    "points_awarded": response.json()["points_awarded"],
                }
            ],
        )

    def test_quiz_load_without_a_part_is_rejected_for_a_multi_part_lecture(self):
        response = self.client.get(f"/api/lectures/{self.lecture.id}/quiz/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("played in parts", response.json()["detail"])

    def test_missing_part_on_a_multi_part_lecture_is_rejected(self):
        question = self.questions[0]
        response = self.client.post(
            f"/api/lectures/{self.lecture.id}/questions/{question.id}/start/"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("played in parts", response.json()["detail"])
        response = self.client.post(
            f"/api/lectures/{self.lecture.id}/answers/",
            {"question_id": question.id, "chosen_index": 0},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Attempt.objects.exists())

    def test_review_shows_the_last_attempt_text_and_points(self):
        question = self.questions[0]
        self.quiz(1)
        attempt = Attempt.objects.get(user=self.student, part_index=0)
        attempt.choice_orders = {
            str(item.id): [0, 1, 2, 3] for item in self.questions[:10]
        }
        attempt.question_order = [item.id for item in self.questions[:10]]
        attempt.save()
        for item in self.questions[:10]:
            chosen = 0 if item.id == question.id else 1
            response = self.answer(item, chosen, part=1)
            self.assertEqual(response.status_code, 201)

        # Replay the part and miss every question, including the one that
        # was correct on the first play. The review shows this later attempt.
        self.quiz(1)
        replay = Attempt.objects.get(
            user=self.student, part_index=0, completed_at__isnull=True
        )
        replay.choice_orders = {
            str(item.id): [0, 1, 2, 3] for item in self.questions[:10]
        }
        replay.question_order = [item.id for item in self.questions[:10]]
        replay.save()
        for item in self.questions[:10]:
            response = self.answer(item, 1, part=1)
            self.assertEqual(response.status_code, 201)

        review = self.client.get(
            f"/api/lectures/{self.lecture.id}/parts/1/review/"
        )
        self.assertEqual(review.status_code, 200)
        body = review.json()
        self.assertEqual(body["part"], 1)
        self.assertEqual(body["question_count"], 10)
        first = next(item for item in body["questions"] if item["id"] == question.id)
        self.assertEqual(first["prompt"], question.prompt)
        self.assertEqual(first["your_answer"], "Bravo")
        self.assertEqual(first["correct_answer"], "Alpha")
        self.assertFalse(first["is_correct"])
        self.assertEqual(first["points_awarded"], 0)
        self.assertEqual(body["total_points"], 0)

        self.client.force_authenticate(self.other)
        hidden = self.client.get(
            f"/api/lectures/{self.lecture.id}/parts/1/review/"
        )
        self.assertEqual(hidden.status_code, 404)
        self.assertNotIn("Bravo", hidden.content.decode())

    def test_first_attempt_of_each_part_counts_and_replays_do_not(self):
        self._play_part(1, correct=True)
        standings = {
            row["user"].id: row["points"]
            for row in class_standings(self.classroom)
        }
        first_total = standings[self.student.id]
        self.assertGreater(first_total, 0)

        self._play_part(1, correct=False)
        standings = {
            row["user"].id: row["points"]
            for row in class_standings(self.classroom)
        }
        self.assertEqual(standings[self.student.id], first_total)

        self._play_part(2, correct=True)
        standings = {
            row["user"].id: row["points"]
            for row in class_standings(self.classroom)
        }
        self.assertGreater(standings[self.student.id], first_total)

        stats = build_class_stats(self.classroom, self.student)
        lecture = next(item for item in stats["lectures"] if item["id"] == self.lecture.id)
        self.assertEqual(lecture["part_count"], 3)
        self.assertTrue(lecture["parts"][0]["completed"])
        self.assertTrue(lecture["parts"][1]["completed"])
        self.assertFalse(lecture["parts"][2]["completed"])
        self.assertEqual(stats["quizzes_played"], 2)
        self.assertEqual(stats["quizzes_total"], 3)
        self.assertGreater(lecture["parts"][0]["best_score"], 0)
        # The replay scored 0, so the shown best score stays the first play.
        self.assertEqual(lecture["parts"][0]["best_score"], first_total)

        board = self.client.get(
            reverse("class-leaderboard", kwargs={"pk": self.classroom.pk})
        )
        mine = next(row for row in board.json() if row["is_current_user"])
        self.assertEqual(mine["points"], standings[self.student.id])

    def test_a_new_part_does_not_keep_the_previous_part_streak(self):
        # Three correct answers in part 1 arm the streak bonus.
        for question in self.questions[:3]:
            self._answer_known(question, part=1, correct=True)
        third = Answer.objects.filter(attempt__user=self.student).order_by("id").last()
        self.assertGreaterEqual(third.points_awarded, 150)

        response = self._answer_known(self.questions[10], part=2, correct=True)
        self.assertEqual(response.json()["points_awarded"], 100)

    def test_legacy_attempt_that_spans_parts_is_not_counted_twice(self):
        legacy = Attempt.objects.create(
            user=self.student,
            lecture=self.lecture,
            part_index=0,
            total_points=420,
            completed_at=timezone.now(),
        )
        for question in self.questions:
            Answer.objects.create(
                attempt=legacy,
                question=question,
                chosen_index=0,
                is_correct=True,
                time_taken_ms=1000,
                points_awarded=10,
            )
        self._play_part(2, correct=True)
        later = Attempt.objects.get(user=self.student, part_index=1)
        self.assertFalse(later.is_first)
        points = next(
            row["points"]
            for row in class_standings(self.classroom)
            if row["user"].id == self.student.id
        )
        self.assertEqual(points, 420)

    def _answer_known(self, question, part, correct):
        self.quiz(part)
        attempt = Attempt.objects.get(
            user=self.student,
            part_index=part - 1,
            completed_at__isnull=True,
        )
        permutation = attempt.choice_orders[str(question.id)]
        shown = permutation.index(question.correct_index)
        chosen = shown if correct else (shown + 1) % 4
        return self.answer(question, chosen, part)

    def _play_part(self, part, correct):
        size = part_sizes(30)[part - 1]
        start = sum(part_sizes(30)[: part - 1])
        for question in self.questions[start:start + size]:
            response = self._answer_known(question, part, correct)
            self.assertEqual(response.status_code, 201, response.content)
        return response


class OnePartCompatibilityTests(APITestCase):
    def test_omitted_part_still_plays_a_short_lecture_in_stored_order(self):
        classroom = Classroom.objects.create(name="Short")
        lecture = Lecture.objects.create(
            classroom=classroom,
            title="Agile",
            published_at=timezone.now() - timedelta(hours=1),
        )
        add_questions(lecture, 5)
        question = lecture.questions.order_by("position", "id").first()
        student = make_student("sam", classroom)
        self.client.force_authenticate(student)

        quiz = self.client.get(f"/api/lectures/{lecture.id}/quiz/")
        self.assertIsNone(quiz.json()["part"])
        self.assertEqual(quiz.json()["part_count"], 1)
        self.assertEqual(quiz.json()["questions"][0]["choices"], ["A", "B", "C", "D"])

        from .testing import answer

        response = answer(self.client, lecture, question, question.correct_index)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["is_correct"])
        self.assertEqual(response.json()["correct_index"], question.correct_index)
        self.assertEqual(
            Answer.objects.get().chosen_index,
            question.correct_index,
        )
