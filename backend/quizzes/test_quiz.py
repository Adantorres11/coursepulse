from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from classrooms.models import Classroom
from .models import Lecture, Question
from .test_lectures import add_questions


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
        self.assertEqual(set(body), {"lecture_id", "title", "questions"})
        self.assertEqual(body["lecture_id"], lecture.id)
        self.assertEqual(body["title"], "A Lecture")
        question = body["questions"][0]
        self.assertEqual(
            set(question),
            {"id", "prompt", "choices", "correct_index", "difficulty"},
        )
        self.assertEqual(question["choices"], ["A", "B", "C", "D"])
        self.assertEqual(question["correct_index"], 0)
        self.assertEqual(question["difficulty"], "easy")

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
