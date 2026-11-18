import re

from django.test import TestCase, override_settings
from django.utils import timezone

from quizzes.job_errors import QUIZ_LOCKED
from quizzes.models import Attempt, Lecture, Question
from quizzes.question_rules import original_of
from quizzes.question_testing import (
    FakeModel,
    QuestionJobMixin,
    concept_payload,
    make_question,
    ok,
    question_payload,
)
from quizzes.testing import make_student

GENERATION_KEYS = {
    "concept",
    "concept_id",
    "pattern",
    "reason",
    "gotcha",
    "distractor_types",
    "section",
    "model",
    "original",
}


def questions_reply(concept_id, numbers):
    return ok(question_payload(*[make_question(concept_id, n) for n in numbers]))


def default_model():
    return FakeModel(
        concepts=[ok(concept_payload("Alpha")), ok(concept_payload("Beta"))],
        questions=[questions_reply("c1", range(4)), questions_reply("c2", range(4, 8))],
    )


def asked_count(call):
    return int(re.search(r"Questions to write: (\d+)", call["user_input"]).group(1))


@override_settings(
    QUESTION_WORDS_PER_QUESTION=100,
    QUESTION_MIN_COUNT=4,
    QUESTION_MAX_COUNT=8,
    QUESTION_FLOOR_COUNT=2,
    QUESTION_MAX_COST_USD=0.25,
    QUESTION_MODEL="gpt-6-luna",
)
class RunQuestionGenerationTests(QuestionJobMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.model = default_model()

    def stage(self, schema_name):
        return [call for call in self.model.calls if call["schema_name"] == schema_name]

    def add_question(self, lecture, n, position, generated=True, **over):
        values = {
            "prompt": f"Existing question {n}?",
            "choices": [f"Existing right {n}", f"Existing no {n}a", f"Existing no {n}b", f"Existing no {n}c"],
            "correct_index": 0,
            "difficulty": "easy",
        }
        generation = None
        if generated:
            generation = {"concept_id": "c1", "pattern": "purpose", "original": original_of(**values)}
        values.update(over)
        return Question.objects.create(
            lecture=lecture, position=position, generation=generation, **values
        )

    def test_success_saves_ready_drafts(self):
        lecture = self.make_lecture()

        self.assertTrue(self.run_job(lecture))

        self.assertEqual(lecture.status, "ready")
        self.assertEqual(lecture.job_token, "")
        self.assertEqual(lecture.progress_message, "")
        self.assertEqual(lecture.error_message, "")
        self.assertEqual(lecture.notice, "")
        self.assertIsNone(lecture.published_at)
        questions = list(lecture.questions.all())
        self.assertEqual(len(questions), 6)
        self.assertEqual([q.position for q in questions], list(range(6)))
        for question in questions:
            question.full_clean()

    def test_saved_generation_data(self):
        lecture = self.make_lecture()

        self.run_job(lecture)

        for question in lecture.questions.all():
            generation = question.generation
            self.assertEqual(set(generation), GENERATION_KEYS)
            self.assertEqual(
                set(generation["section"]), {"index", "start_seconds", "end_seconds"}
            )
            self.assertEqual(generation["model"], "gpt-6-luna")
            self.assertIn(generation["concept"], {"Alpha", "Beta"})
            self.assertIsNone(generation["distractor_types"][question.correct_index])
            self.assertEqual(
                generation["original"],
                original_of(
                    question.prompt, question.choices, question.correct_index, question.difficulty
                ),
            )

    def test_calls_use_stage_efforts(self):
        lecture = self.make_lecture()

        self.run_job(lecture)

        concepts, questions = self.stage("concepts"), self.stage("questions")
        self.assertEqual(len(concepts), 2)
        self.assertEqual(len(questions), 2)
        self.assertTrue(all(call["effort"] == "low" for call in concepts))
        self.assertTrue(all(call["effort"] == "medium" for call in questions))
        self.assertTrue(
            all(call["cache_key"] == f"lecture-{lecture.id}" for call in self.model.calls)
        )
        for call in questions:
            self.assertIn('"c1"', call["user_input"])
            self.assertIn('"c2"', call["user_input"])

    def test_questions_ordered_by_concept(self):
        self.model = FakeModel(
            concepts=[ok(concept_payload("Alpha")), ok(concept_payload("Beta", "Alpha"))],
            questions=[
                ok(question_payload(make_question("c2", 0), make_question("c1", 1),
                                    make_question("c2", 2), make_question("c1", 3))),
                ok(question_payload(make_question("c2", 4), make_question("c1", 5),
                                    make_question("c2", 6), make_question("c1", 7))),
            ],
        )
        lecture = self.make_lecture()

        self.assertTrue(self.run_job(lecture))

        ids = [q.generation["concept_id"] for q in lecture.questions.all()]
        self.assertEqual(len(ids), 6)
        self.assertEqual(ids, sorted(ids))
        self.assertIn("c1", ids)
        self.assertIn("c2", ids)

    def test_rerun_does_not_duplicate(self):
        lecture = self.make_lecture()
        self.run_job(lecture)
        first_ids = set(lecture.questions.values_list("id", flat=True))
        Lecture.objects.filter(pk=lecture.id).update(status="processing", job_token="")
        self.model = default_model()

        self.assertTrue(self.run_job(lecture))

        ids = set(lecture.questions.values_list("id", flat=True))
        self.assertEqual(len(ids), 6)
        self.assertFalse(ids & first_ids)

    def test_hand_written_and_edited_questions_are_kept(self):
        lecture = self.make_lecture()
        hand = self.add_question(lecture, 1, position=5, generated=False)
        edited = self.add_question(lecture, 2, position=9)
        Question.objects.filter(pk=edited.pk).update(prompt="Edited by the professor?")

        self.assertTrue(self.run_job(lecture))

        questions = list(lecture.questions.all())
        self.assertEqual(len(questions), 6)
        self.assertEqual([q.id for q in questions[:2]], [hand.id, edited.id])
        self.assertEqual([q.position for q in questions], list(range(6)))
        self.assertEqual(questions[1].prompt, "Edited by the professor?")
        self.assertTrue(all(q.generation and "model" in q.generation for q in questions[2:]))
        self.assertEqual(sum(asked_count(call) - 1 for call in self.stage("questions")), 4)

    def test_untouched_generated_drafts_are_replaced(self):
        lecture = self.make_lecture()
        old = self.add_question(lecture, 1, position=0)

        self.assertTrue(self.run_job(lecture))

        self.assertFalse(Question.objects.filter(pk=old.pk).exists())
        self.assertEqual(lecture.questions.count(), 6)

    def test_kept_questions_meet_target_skip_calls(self):
        lecture = self.make_lecture()
        for n in range(6):
            self.add_question(lecture, n, position=n, generated=False)

        self.assertTrue(self.run_job(lecture))

        self.assertEqual(self.model.calls, [])
        self.assertEqual(lecture.status, "ready")
        self.assertEqual(lecture.notice, "Kept your 6 questions. No new questions were needed.")
        self.assertEqual(lecture.questions.count(), 6)

    def assert_locked(self, lecture, before):
        self.assertFalse(self.run_job(lecture))
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, QUIZ_LOCKED)
        self.assertEqual(lecture.job_token, "")
        self.assertEqual(self.model.calls, [])
        self.assertEqual(
            list(lecture.questions.values_list("id", "prompt", "position", "generation")), before
        )

    def test_published_lecture_is_not_touched(self):
        lecture = self.make_lecture(published_at=timezone.now())
        self.add_question(lecture, 1, position=0)
        before = list(lecture.questions.values_list("id", "prompt", "position", "generation"))

        self.assert_locked(lecture, before)

    def test_lecture_with_attempts_is_not_touched(self):
        lecture = self.make_lecture()
        self.add_question(lecture, 1, position=0)
        Attempt.objects.create(user=make_student("sam", self.classroom), lecture=lecture)
        before = list(lecture.questions.values_list("id", "prompt", "position", "generation"))

        self.assert_locked(lecture, before)

    def test_edit_during_run_is_kept(self):
        lecture = self.make_lecture()
        old = self.add_question(lecture, 1, position=0)
        model = self.model

        def edit_after_last_reply(**kwargs):
            reply = model(**kwargs)
            if kwargs["schema_name"] == "questions" and not model.questions:
                Question.objects.filter(pk=old.pk).update(prompt="Edited during the run?")
            return reply

        self.model = edit_after_last_reply

        self.assertTrue(self.run_job(lecture))

        questions = list(lecture.questions.all())
        self.assertEqual(questions[0].id, old.id)
        self.assertEqual(questions[0].prompt, "Edited during the run?")
        self.assertEqual(len(questions), 7)
        self.assertEqual([q.position for q in questions], list(range(7)))
        self.assertTrue(all("model" in q.generation for q in questions[1:]))

    def test_section_without_concepts_gets_no_question_call(self):
        self.model = FakeModel(
            concepts=[ok(concept_payload("Alpha")), ok({"concepts": []})],
            questions=[questions_reply("c1", range(7))],
        )
        lecture = self.make_lecture()

        self.assertTrue(self.run_job(lecture))

        calls = self.stage("questions")
        self.assertEqual(len(calls), 1)
        self.assertEqual(asked_count(calls[0]), 7)
        self.assertEqual(lecture.questions.count(), 6)

    def test_runs_without_raw_transcript(self):
        self.model = FakeModel(
            concepts=[ok(concept_payload("Alpha"))],
            questions=[questions_reply("c1", range(7))],
        )
        lecture = self.make_lecture(raw_transcript=None)

        self.assertTrue(self.run_job(lecture))

        self.assertEqual(lecture.status, "ready")
        self.assertEqual(lecture.questions.count(), 6)
        section = lecture.questions.first().generation["section"]
        self.assertEqual(section, {"index": 0, "start_seconds": None, "end_seconds": None})

    def test_lost_ownership_saves_nothing(self):
        lecture = self.make_lecture()
        model = self.model

        def take_over(**kwargs):
            if kwargs["schema_name"] == "questions":
                Lecture.objects.filter(pk=lecture.id).update(job_token="other")
            return model(**kwargs)

        self.model = take_over

        self.assertFalse(self.run_job(lecture))

        self.assertEqual(lecture.questions.count(), 0)
        self.assertEqual(lecture.status, "processing")
        self.assertEqual(lecture.job_token, "other")

    def test_logs_have_no_question_text(self):
        lecture = self.make_lecture()

        with self.assertLogs("quizzes", "INFO") as logs:
            self.assertTrue(self.run_job(lecture))

        prompts = list(lecture.questions.values_list("prompt", flat=True))
        words = lecture.transcript.split()
        for line in logs.output:
            for prompt in prompts:
                self.assertNotIn(prompt, line)
            self.assertNotIn(lecture.transcript, line)
            self.assertNotIn(" ".join(words[:5]), line)
        summary = [line for line in logs.output if "cost_usd=" in line]
        self.assertEqual(len(summary), 1)
        self.assertIn("effort=low/medium", summary[0])
