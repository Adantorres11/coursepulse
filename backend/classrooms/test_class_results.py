from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Profile
from classrooms.models import Classroom, Enrollment
from quizzes.models import Attempt, Answer, Lecture, Question


class ClassResultsTests(APITestCase):
    def setUp(self):
        self.professor = self.create_user(
            "professor", "professor"
        )
        self.other_professor = self.create_user(
            "other_professor", "professor"
        )
        self.student = self.create_user(
            "student", "student"
        )
        self.second_student = self.create_user(
            "student2", "student"
        )

        self.classroom = Classroom.objects.create(
            name="Software Engineering",
            professor=self.professor,
        )

        Enrollment.objects.create(
            user=self.student,
            classroom=self.classroom,
        )
        Enrollment.objects.create(
            user=self.second_student,
            classroom=self.classroom,
        )

        self.lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Lecture 1",
            published_at=timezone.now(),
        )

        self.question = Question.objects.create(
            lecture=self.lecture,
            prompt="What is 2 + 2?",
            choices=["4", "3", "5", "6"],
            correct_index=0,
            difficulty="easy",
            position=1,
        )

        self.url = reverse(
            "class-results",
            args=[self.classroom.id],
        )

    def create_user(self, username, role):
        user = User.objects.create_user(
            username=username,
            password="testpass",
        )
        Profile.objects.create(user=user, role=role)
        return user

    def create_attempt(self, user, question, correct,
                       completed=True):
        points = 100 if correct else 0

        attempt = Attempt.objects.create(
            user=user,
            lecture=question.lecture,
            total_points=points,
            completed_at=(
                timezone.now() if completed else None
            ),
        )

        Answer.objects.create(
            attempt=attempt,
            question=question,
            chosen_index=0 if correct else 1,
            is_correct=correct,
            time_taken_ms=1000,
            points_awarded=points,
        )

        return attempt

    def test_professor_can_view_results(self):
        # First attempt and two retakes.
        self.create_attempt(
            self.student, self.question, True
        )
        self.create_attempt(
            self.student, self.question, True
        )
        self.create_attempt(
            self.student, self.question, False
        )

        # An unfinished attempt should not affect results.
        second_lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="Lecture 2",
            published_at=timezone.now(),
        )

        second_question = Question.objects.create(
            lecture=second_lecture,
            prompt="What is 3 + 3?",
            choices=["6", "7", "8", "9"],
            correct_index=0,
            difficulty="easy",
            position=1,
        )

        self.create_attempt(
            self.student,
            second_question,
            True,
            completed=False,
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        students = response.data["students"]
        self.assertEqual(len(students), 2)

        self.assertEqual(students[0]["name"], "student")
        self.assertEqual(students[0]["total_points"], 100)
        self.assertEqual(students[0]["quizzes_played"], 1)

        self.assertEqual(students[1]["total_points"], 0)
        self.assertEqual(students[1]["quizzes_played"], 0)

        lectures = response.data["lectures"]
        self.assertEqual(len(lectures), 2)

        question = lectures[0]["questions"][0]

        # Retakes count once. Accuracy is the share of students whose
        # best completed attempt got the question right.
        self.assertEqual(question["answer_count"], 1)
        self.assertEqual(question["correct_count"], 1)
        self.assertEqual(question["accuracy_percent"], 100)

        played = students[0]["lectures"]
        self.assertEqual(played[0]["lecture_id"], self.lecture.id)
        self.assertTrue(played[0]["played"])
        self.assertEqual(played[0]["score"], 100)
        self.assertEqual(played[0]["correct_count"], 1)
        self.assertEqual(played[1]["lecture_id"], second_lecture.id)
        self.assertFalse(played[1]["played"])
        self.assertIsNone(played[1]["score"])
        self.assertIsNone(played[1]["correct_count"])

        skipped = students[1]["lectures"]
        self.assertFalse(skipped[0]["played"])
        self.assertFalse(skipped[1]["played"])

        unanswered = lectures[1]["questions"][0]
        self.assertEqual(unanswered["answer_count"], 0)
        self.assertIsNone(unanswered["accuracy_percent"])

    def test_empty_class_results(self):
        classroom = Classroom.objects.create(
            name="Empty Class",
            professor=self.professor,
        )

        self.client.force_authenticate(user=self.professor)

        response = self.client.get(
            reverse("class-results", args=[classroom.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["students"], [])
        self.assertEqual(response.data["lectures"], [])

    def test_other_class_results_not_included(self):
        other_class = Classroom.objects.create(
            name="Other Class",
            professor=self.professor,
        )

        Enrollment.objects.create(
            user=self.student,
            classroom=other_class,
        )

        other_lecture = Lecture.objects.create(
            classroom=other_class,
            title="Other Lecture",
        )

        other_question = Question.objects.create(
            lecture=other_lecture,
            prompt="What is 1 + 1?",
            choices=["2", "3", "4", "5"],
            correct_index=0,
            difficulty="easy",
        )

        self.create_attempt(
            self.student, other_question, True
        )

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        student = next(
            item for item in response.data["students"]
            if item["student_id"] == self.student.id
        )

        self.assertEqual(student["total_points"], 0)
        self.assertEqual(student["quizzes_played"], 0)
        self.assertEqual(len(response.data["lectures"]), 1)

    def test_other_professor_cannot_access_results(self):
        self.client.force_authenticate(
            user=self.other_professor
        )
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_results(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_unknown_class(self):
        self.client.force_authenticate(user=self.professor)

        response = self.client.get(
            reverse(
                "class-results",
                args=[self.classroom.id + 10000],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    def test_each_student_counts_once_toward_question_accuracy(self):
        wrong = Question.objects.create(
            lecture=self.lecture,
            prompt="What is 1 + 1?",
            choices=["2", "3", "4", "5"],
            correct_index=0,
            difficulty="easy",
            position=2,
        )
        self.create_attempt(self.student, self.question, True)
        Answer.objects.create(
            attempt=Attempt.objects.get(user=self.student),
            question=wrong,
            chosen_index=1,
            is_correct=False,
            time_taken_ms=1000,
            points_awarded=0,
        )
        missed = Attempt.objects.create(
            user=self.second_student,
            lecture=self.lecture,
            total_points=0,
            completed_at=timezone.now(),
        )
        Answer.objects.create(
            attempt=missed,
            question=self.question,
            chosen_index=1,
            is_correct=False,
            time_taken_ms=1000,
            points_awarded=0,
        )
        Answer.objects.create(
            attempt=missed,
            question=wrong,
            chosen_index=0,
            is_correct=True,
            time_taken_ms=1000,
            points_awarded=100,
        )
        missed.total_points = 100
        missed.save(update_fields=["total_points"])

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        questions = {
            item["question_id"]: item
            for item in response.data["lectures"][0]["questions"]
        }
        self.assertEqual(questions[self.question.id]["answer_count"], 2)
        self.assertEqual(questions[self.question.id]["correct_count"], 1)
        self.assertEqual(
            questions[self.question.id]["accuracy_percent"], 50
        )
        self.assertEqual(questions[wrong.id]["accuracy_percent"], 50)

        rows = {
            item["student_id"]: item for item in response.data["students"]
        }
        first = rows[self.student.id]["lectures"][0]
        second = rows[self.second_student.id]["lectures"][0]
        self.assertEqual(first["score"], 100)
        self.assertEqual(first["correct_count"], 1)
        self.assertEqual(second["score"], 100)
        self.assertEqual(second["correct_count"], 1)

    def test_best_attempt_is_the_lecture_score_and_first_attempt_is_the_total(self):
        self.create_attempt(self.student, self.question, False)
        retry = self.create_attempt(self.student, self.question, True)

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)
        student = response.data["students"][0]

        self.assertEqual(student["total_points"], 0)
        lecture = student["lectures"][0]
        self.assertTrue(lecture["played"])
        self.assertEqual(lecture["score"], retry.total_points)
        self.assertEqual(lecture["correct_count"], 1)
        self.assertEqual(
            response.data["lectures"][0]["questions"][0]["accuracy_percent"],
            100,
        )

    def test_unpublished_lecture_is_left_out_of_the_report(self):
        draft = Lecture.objects.create(
            classroom=self.classroom,
            title="Draft",
        )
        draft_question = Question.objects.create(
            lecture=draft,
            prompt="Hidden?",
            choices=["Yes", "No", "Maybe", "Later"],
            correct_index=0,
            difficulty="easy",
            position=1,
        )
        self.create_attempt(self.student, draft_question, True)

        self.client.force_authenticate(user=self.professor)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["lecture_id"] for item in response.data["lectures"]],
            [self.lecture.id],
        )
        student = next(
            item for item in response.data["students"]
            if item["student_id"] == self.student.id
        )
        self.assertEqual(student["total_points"], 0)
        self.assertEqual(len(student["lectures"]), 1)
        self.assertFalse(student["lectures"][0]["played"])