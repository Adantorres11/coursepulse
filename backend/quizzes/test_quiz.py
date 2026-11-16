from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, APITestCase

from classrooms.models import Classroom
from .grading import get_open_attempt
from .models import Lecture, Question
from .serializers import QuizSerializer
from .test_lectures import add_questions
from .testing import answer, make_student


class LectureQuizTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")
        cls.now = timezone.now()

    def make_lecture(self, published_at, questions=1):
        lecture = Lecture.objects.create(
            classroom=self.classroom,
            title="A Lecture",
            published_at=published_at,
        )
        add_questions(lecture, questions)
        return lecture

    def url(self, lecture_id):
        return f"/api/lectures/{lecture_id}/quiz/"

    def test_quiz_has_contract_fields(self):
        lecture = self.make_lecture(self.now - timedelta(days=1))

        response = self.client.get(self.url(lecture.id))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            set(body),
            {
                "lecture_id",
                "title",
                "questions",
                "answered_question_ids",
                "total_points",
            },
        )
        self.assertEqual(body["lecture_id"], lecture.id)
        self.assertEqual(body["title"], "A Lecture")
        question = body["questions"][0]
        self.assertEqual(
            set(question),
            {"id", "prompt", "choices", "difficulty"},
        )
        self.assertEqual(question["choices"], ["A", "B", "C", "D"])
        self.assertEqual(question["difficulty"], "easy")

    def test_questions_do_not_include_correct_index(self):
        lecture = self.make_lecture(self.now - timedelta(days=1))

        response = self.client.get(self.url(lecture.id))

        self.assertEqual(response.status_code, 200)
        question = response.json()["questions"][0]
        self.assertEqual(set(question), {"id", "prompt", "choices", "difficulty"})
        self.assertNotIn("correct_index", response.content.decode())

    def test_questions_follow_position_then_id(self):
        lecture = self.make_lecture(self.now - timedelta(days=1), questions=0)
        third = Question.objects.create(
            lecture=lecture, prompt="third", choices=["A", "B", "C", "D"],
            correct_index=0, difficulty="easy", position=3,
        )
        first = Question.objects.create(
            lecture=lecture, prompt="first", choices=["A", "B", "C", "D"],
            correct_index=0, difficulty="easy", position=1,
        )
        tie = Question.objects.create(
            lecture=lecture, prompt="tie", choices=["A", "B", "C", "D"],
            correct_index=0, difficulty="easy", position=1,
        )

        response = self.client.get(self.url(lecture.id))

        ids = [question["id"] for question in response.json()["questions"]]
        self.assertEqual(ids, [first.id, tie.id, third.id])

    def test_unknown_lecture_returns_404(self):
        response = self.client.get(self.url(99999))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_unpublished_lecture_returns_404(self):
        lecture = self.make_lecture(None)

        self.assertEqual(self.client.get(self.url(lecture.id)).status_code, 404)

    def test_future_lecture_returns_404(self):
        lecture = self.make_lecture(self.now + timedelta(days=1))

        self.assertEqual(self.client.get(self.url(lecture.id)).status_code, 404)

    def test_lecture_without_questions_returns_404(self):
        lecture = self.make_lecture(self.now - timedelta(days=1), questions=0)

        self.assertEqual(self.client.get(self.url(lecture.id)).status_code, 404)


class QuizProgressTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        classroom = Classroom.objects.create(name="Any Class")
        cls.lecture = Lecture.objects.create(
            classroom=classroom,
            title="A Lecture",
            published_at=timezone.now() - timedelta(days=1),
        )
        add_questions(cls.lecture, 3)
        cls.questions = list(cls.lecture.questions.order_by("position", "id"))
        cls.student = make_student("one", classroom)
        cls.other = make_student("two", classroom)
        cls.other_lecture = Lecture.objects.create(
            classroom=classroom,
            title="Another Lecture",
            published_at=timezone.now() - timedelta(days=1),
        )
        add_questions(cls.other_lecture, 1)

    def answer(self, question):
        return answer(self.client, self.lecture, question, question.correct_index)

    def get_quiz(self):
        return self.client.get(f"/api/lectures/{self.lecture.id}/quiz/").json()

    def test_quiz_reports_progress_of_the_open_attempt(self):
        self.client.force_authenticate(self.student)
        self.answer(self.questions[0])
        self.answer(self.questions[1])

        body = self.get_quiz()

        self.assertEqual(
            sorted(body["answered_question_ids"]),
            sorted([self.questions[0].id, self.questions[1].id]),
        )
        self.assertEqual(body["total_points"], 200)

    def test_quiz_progress_is_empty_when_logged_out(self):
        body = self.get_quiz()

        self.assertEqual(body["answered_question_ids"], [])
        self.assertEqual(body["total_points"], 0)

    def test_quiz_progress_resets_after_completion(self):
        self.client.force_authenticate(self.student)
        for question in self.questions:
            self.answer(question)

        body = self.get_quiz()

        self.assertEqual(body["answered_question_ids"], [])
        self.assertEqual(body["total_points"], 0)

    def test_quiz_progress_is_per_student(self):
        self.client.force_authenticate(self.student)
        self.answer(self.questions[0])
        self.client.force_authenticate(self.other)

        body = self.get_quiz()

        self.assertEqual(body["answered_question_ids"], [])
        self.assertEqual(body["total_points"], 0)

    def test_quiz_loads_the_open_attempt_once(self):
        self.client.force_authenticate(self.student)
        self.answer(self.questions[0])

        with patch(
            "quizzes.serializers.get_open_attempt", wraps=get_open_attempt
        ) as spy:
            body = self.get_quiz()

        self.assertEqual(spy.call_count, 1)
        self.assertEqual(body["answered_question_ids"], [self.questions[0].id])

    def test_logged_out_quiz_does_not_look_up_an_attempt(self):
        with patch(
            "quizzes.serializers.get_open_attempt", wraps=get_open_attempt
        ) as spy:
            self.get_quiz()

        self.assertEqual(spy.call_count, 0)

    def test_serializer_reused_for_two_lectures_uses_each_attempt(self):
        self.client.force_authenticate(self.student)
        self.answer(self.questions[0])
        request = APIRequestFactory().get("/")
        request.user = self.student
        serializer = QuizSerializer(context={"request": request})

        first = serializer.to_representation(self.lecture)
        second = serializer.to_representation(self.other_lecture)

        self.assertEqual(first["answered_question_ids"], [self.questions[0].id])
        self.assertEqual(second["answered_question_ids"], [])
        self.assertEqual(second["total_points"], 0)
