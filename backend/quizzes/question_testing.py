"""Shared fixtures for the run_question_generation tests. The model is always scripted."""

import contextlib
from unittest import mock

from classrooms.models import Classroom
from quizzes.jobs import job_logger
from quizzes.models import Lecture
from quizzes.question_client import Reply, Usage
from quizzes.question_prompts import PATTERNS
from quizzes.question_rules import DIFFICULTIES

TOKEN = "gen-1"


@contextlib.contextmanager
def fake_lock(lecture_id, token, **kwargs):
    yield True


def concept_payload(*names: str) -> dict:
    return {
        "concepts": [
            {
                "name": name,
                "summary": f"What {name} is.",
                "key_facts": [f"A fact about {name}."],
                "mechanism": f"How {name} works.",
                "contrasts": [],
                "formulas_code_procedures": [],
                "warned_mistakes": [],
            }
            for name in names
        ]
    }


def question_payload(*qs: dict) -> dict:
    return {"questions": list(qs)}


def make_question(concept_id: str, n: int, **over) -> dict:
    """A valid question. n makes the prompt, the answer, and the grid cell unique."""
    question = {
        "prompt": f"Which statement about topic {n} of {concept_id} is true?",
        "choices": [
            f"True claim {n}",
            f"False claim {n}a",
            f"False claim {n}b",
            f"False claim {n}c",
        ],
        "correct_index": 0,
        "difficulty": DIFFICULTIES[n % 3],
        "reason": f"Claim {n} is the true one.",
        "concept_id": concept_id,
        "pattern": PATTERNS[n % len(PATTERNS)],
        "gotcha": False,
        "distractor_types": [None, "wrong_mechanism", "opposite_effect", "generic_benefit"],
    }
    question.update(over)
    return question


def ok(data: dict, input_tokens=1000, cached=0, output=500) -> Reply:
    return Reply(data, Usage(input_tokens, cached, output), "")


def bad(problem: str = "bad_json") -> Reply:
    return Reply(None, Usage(1000, 0, 500), problem)


class FakeModel:
    """Scripted stand-in for question_client.ask, patched at quizzes.question_generation.ask."""

    def __init__(self, concepts: list[Reply], questions: list[Reply], distractors=()):
        self.concepts = list(concepts)
        self.questions = list(questions)
        self.distractors = list(distractors)  # empty by default: no rewrite call expected
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> Reply:
        self.calls.append(kwargs)
        script = {
            "concepts": self.concepts,
            "distractors": self.distractors,
        }.get(kwargs["schema_name"], self.questions)
        if not script:
            raise AssertionError(f"unexpected {kwargs['schema_name']} call")
        return script.pop(0)


def questions_reply(concept_id: str, numbers) -> Reply:
    return ok(question_payload(*[make_question(concept_id, n) for n in numbers]))


def default_model() -> "FakeModel":
    """Two sections, concepts Alpha (c1) and Beta (c2), and four questions for each."""
    return FakeModel(
        concepts=[ok(concept_payload("Alpha")), ok(concept_payload("Beta"))],
        questions=[questions_reply("c1", range(4)), questions_reply("c2", range(4, 8))],
    )


class QuestionJobMixin:
    """Patches ask with self.model and the lock with a fake that yields True. Creates self.classroom.

    `ask` calls whatever `self.model` holds at call time, so a test may set or wrap it
    in its body.
    """

    model = None

    def setUp(self):
        super().setUp()
        self.classroom = Classroom.objects.create(name="Any Class")
        patches = [
            mock.patch(
                "quizzes.question_generation.ask",
                side_effect=lambda **kwargs: self.model(**kwargs),
            ),
            mock.patch("quizzes.question_generation.lecture_lock", fake_lock),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def make_lecture(self, sections: int = 2, words_per_section: int = 300, **fields) -> Lecture:
        texts = [
            " ".join(f"s{i}w{j}" for j in range(words_per_section)) + "."
            for i in range(sections)
        ]
        values = {
            "title": "Week 3 Graphs",
            "status": "processing",
            "job_token": "",
            "transcript": " ".join(texts),
            "raw_transcript": {
                "chunks": [
                    {"index": i, "start": i * 600.0, "end": (i + 1) * 600.0, "text": text}
                    for i, text in enumerate(texts)
                ]
            },
        }
        values.update(fields)
        return Lecture.objects.create(classroom=self.classroom, **values)

    def run_job(self, lecture) -> bool:
        from quizzes.question_generation import run_question_generation

        result = run_question_generation(lecture.id, TOKEN, 0, job_logger(lecture.id, TOKEN, 0))
        lecture.refresh_from_db()
        return result
