from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from classrooms.models import Classroom
from .models import Lecture, Question


def add_questions(lecture, count):
    for position in range(count):
        Question.objects.create(
            lecture=lecture,
            prompt=f"Question {position}?",
            choices=["A", "B", "C", "D"],
            correct_index=0,
            difficulty="easy",
            position=position,
        )


class LectureListTests(TestCase):
    url = "/api/lectures/"

    @classmethod
    def setUpTestData(cls):
        cls.classroom = Classroom.objects.create(name="Any Class")
        cls.now = timezone.now()

    def make_lecture(self, title, published_at, questions=1):
        lecture = Lecture.objects.create(
            classroom=self.classroom,
            title=title,
            published_at=published_at,
        )
        add_questions(lecture, questions)
        return lecture

    def test_empty_list_when_nothing_is_published(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_published_lecture_has_contract_fields(self):
        lecture = self.make_lecture(
            "Published", self.now - timedelta(hours=1), questions=3
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        item = response.json()[0]
        self.assertEqual(
            set(item),
            {
                "id",
                "title",
                "classroom_id",
                "classroom",
                "published_at",
                "question_count",
            },
        )
        self.assertEqual(item["id"], lecture.id)
        self.assertEqual(item["title"], "Published")
        self.assertEqual(item["classroom_id"], self.classroom.id)
        self.assertEqual(item["classroom"], "Any Class")
        self.assertEqual(item["question_count"], 3)

    def test_draft_lecture_is_excluded(self):
        self.make_lecture("Draft", None)
        self.assertEqual(self.client.get(self.url).json(), [])

    def test_future_lecture_is_excluded(self):
        self.make_lecture("Future", self.now + timedelta(days=1))
        self.assertEqual(self.client.get(self.url).json(), [])

    def test_published_lecture_without_questions_is_excluded(self):
        self.make_lecture("Empty", self.now - timedelta(hours=1), questions=0)
        self.assertEqual(self.client.get(self.url).json(), [])

    def test_newest_published_lecture_comes_first(self):
        older = self.make_lecture("Older", self.now - timedelta(days=2))
        newer = self.make_lecture("Newer", self.now - timedelta(days=1))
        ids = [item["id"] for item in self.client.get(self.url).json()]
        self.assertEqual(ids, [newer.id, older.id])
