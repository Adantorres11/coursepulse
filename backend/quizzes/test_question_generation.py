import contextlib
import copy
import json
import re
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from celery.exceptions import SoftTimeLimitExceeded

from quizzes.job_errors import (
    BAD_OUTPUT,
    INTERRUPTED,
    NO_CONCEPTS,
    QUESTIONS_BAD_KEY,
    QUESTIONS_BUSY,
    QUESTIONS_TOO_EXPENSIVE,
    QUIZ_LOCKED,
    TIMEOUT,
    UNEXPECTED,
    PermanentError,
    TransientError,
)
from quizzes.jobs import heartbeat as real_heartbeat
from quizzes.jobs import job_logger
from quizzes.models import Attempt, Lecture, Question
from quizzes.question_client import Reply, Usage
from quizzes.question_prompts import (
    DISTRACTOR_INSTRUCTIONS,
    DISTRACTOR_SCHEMA,
    GOTCHA_INSTRUCTIONS,
    QUESTION_INSTRUCTIONS,
)
from quizzes.question_rules import balance_positions as real_balance
from quizzes.question_rules import original_of
from quizzes.question_testing import (
    TOKEN,
    FakeModel,
    bad,
    QuestionJobMixin,
    concept_payload,
    default_model,
    make_question,
    ok,
    question_payload,
    questions_reply,
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


def logistics(concept_id, n):
    """A question the checks drop as speaker_or_logistics."""
    return make_question(concept_id, n, prompt=f"Which homework rule {n} is true?")


def mixed_reply(concept_id, good, dropped):
    return ok(question_payload(
        *[make_question(concept_id, n) for n in good],
        *[logistics(concept_id, n) for n in dropped],
    ))


def gotcha_reply(concept_id, numbers):
    return ok(question_payload(*[make_question(concept_id, n, gotcha=True) for n in numbers]))


def two_concepts():
    return [ok(concept_payload("Alpha")), ok(concept_payload("Beta"))]


def raising(exc):
    def call(**kwargs):
        raise exc
    return call


@contextlib.contextmanager
def busy_lock(lecture_id, token, **kwargs):
    yield False


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

    def test_lost_ownership_while_saving_saves_nothing(self):
        lecture = self.make_lecture()
        old = self.add_question(lecture, 1, position=0)

        def take_over(lecture_id, token, message):
            real_heartbeat(lecture_id, token, message)
            if message == "Saving questions":
                # After the last heartbeat, so only the check inside the save can see it.
                Lecture.objects.filter(pk=lecture_id).update(job_token="other")

        with mock.patch("quizzes.question_generation.heartbeat", side_effect=take_over):
            self.assertFalse(self.run_job(lecture))

        self.assertEqual(list(lecture.questions.values_list("id", flat=True)), [old.id])
        self.assertEqual(lecture.status, "processing")
        self.assertEqual(lecture.job_token, "other")

    def test_publish_during_run_changes_nothing(self):
        lecture = self.make_lecture()
        old = self.add_question(lecture, 1, position=3)
        before = list(lecture.questions.values_list("id", "prompt", "position", "generation"))
        model = self.model

        def publish_after_last_reply(**kwargs):
            reply = model(**kwargs)
            if kwargs["schema_name"] == "questions" and not model.questions:
                Lecture.objects.filter(pk=lecture.id).update(published_at=timezone.now())
            return reply

        self.model = publish_after_last_reply

        self.assertFalse(self.run_job(lecture))

        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, QUIZ_LOCKED)
        self.assertEqual(
            list(lecture.questions.values_list("id", "prompt", "position", "generation")), before
        )
        self.assertTrue(Question.objects.filter(pk=old.pk).exists())

    def test_kept_questions_come_before_section_text(self):
        lecture = self.make_lecture()
        self.add_question(lecture, 1, position=0, generated=False)

        self.run_job(lecture)

        for call in self.stage("questions"):
            text = call["user_input"]
            self.assertLess(text.index("Existing question 1?"), text.index("Questions to write:"))
            self.assertLess(text.index("FULL CONCEPT LIST"), text.index("Existing question 1?"))

    def test_question_calls_ask_for_exact_difficulty_counts(self):
        lecture = self.make_lecture()

        self.run_job(lecture)

        for call in self.stage("questions"):
            self.assertEqual(asked_count(call), 4)
            self.assertIn("Write exactly 4 questions: 1 easy, 2 medium, 1 hard.", call["user_input"])
            self.assertNotIn("30%", call["user_input"])

    def test_later_section_lists_earlier_sections_questions(self):
        lecture = self.make_lecture()

        self.run_job(lecture)

        first, second = self.stage("questions")
        heading = "QUESTIONS FROM OTHER SECTIONS"
        self.assertNotIn(heading, first["user_input"])
        text = second["user_input"]
        for n in range(4):
            question = make_question("c1", n)
            self.assertIn(f"- {question['prompt']} Answer: {question['choices'][0]}", text)
        # The per-call part comes after the cached prefix.
        self.assertLess(text.index("FULL CONCEPT LIST"), text.index(heading))
        self.assertLess(text.index(heading), text.index("SECTION TRANSCRIPT"))
        self.assertIn("even under a different concept", text)

    def test_summary_counts_longest_correct_answers(self):
        def long_first(n):
            return make_question(
                "c1", n, choices=[f"A much longer and fuller claim {n}", "No a", "No b", "No c"]
            )

        self.model = FakeModel(
            two_concepts(),
            [
                ok(question_payload(*[long_first(n) for n in range(4)])),
                questions_reply("c2", range(4, 8)),
            ],
            # The rewrite call returns nothing, so the long answers stay.
            [ok({"distractors": []})],
        )
        lecture = self.make_lecture()

        with self.assertLogs("quizzes", "INFO") as logs:
            self.assertTrue(self.run_job(lecture))

        summary = [line for line in logs.output if "cost_usd=" in line][0]
        generated = lecture.questions.count()
        longest = sum(
            1 for q in lecture.questions.all()
            if q.choices[q.correct_index].startswith("A much longer and fuller claim")
        )
        self.assertGreater(longest, 0)
        self.assertIn(f"longest_correct={longest}/{generated}", summary)

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


@override_settings(
    QUESTION_WORDS_PER_QUESTION=100,
    QUESTION_MIN_COUNT=4,
    QUESTION_MAX_COUNT=8,
    QUESTION_FLOOR_COUNT=2,
    QUESTION_MAX_COST_USD=0.25,
    QUESTION_MODEL="gpt-6-luna",
)
class RecoveryAndErrorTests(QuestionJobMixin, TestCase):
    def section_calls(self, section):
        word = f"s{section}w0 "
        return [
            call for call in self.model.calls
            if call["instructions"] == QUESTION_INSTRUCTIONS and word in call["user_input"]
        ]

    def gotcha_calls(self):
        return [c for c in self.model.calls if c["instructions"] == GOTCHA_INSTRUCTIONS]

    def assert_failed(self, lecture, message):
        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, message)
        self.assertEqual(lecture.job_token, "")
        self.assertEqual(lecture.questions.count(), 0)

    def test_bad_reply_is_reasked_once(self):
        self.model = FakeModel(
            two_concepts(),
            [bad("bad_json"), questions_reply("c1", range(4)), questions_reply("c2", range(4, 8))],
        )
        lecture = self.make_lecture()

        self.assertTrue(self.run_job(lecture))

        self.assertEqual(lecture.status, "ready")
        self.assertEqual(len(self.section_calls(0)), 2)
        self.assertEqual(self.section_calls(0)[0], self.section_calls(0)[1])

    def test_two_bad_replies_fail(self):
        self.model = FakeModel(two_concepts(), [bad("refusal"), bad("incomplete")])
        lecture = self.make_lecture()

        self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, BAD_OUTPUT)

    def test_bad_concept_reply_is_reasked_once(self):
        self.model = FakeModel(
            [bad("bad_json"), *two_concepts()],
            [questions_reply("c1", range(4)), questions_reply("c2", range(4, 8))],
        )
        lecture = self.make_lecture()

        self.assertTrue(self.run_job(lecture))

        concept_calls = [c for c in self.model.calls if c["schema_name"] == "concepts"]
        self.assertEqual(len(concept_calls), 3)
        self.assertEqual(concept_calls[0], concept_calls[1])

    def test_two_bad_concept_replies_fail(self):
        self.model = FakeModel([bad("refusal"), bad("incomplete")], [])
        lecture = self.make_lecture()

        self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, BAD_OUTPUT)

    def test_no_concepts_fails(self):
        self.model = FakeModel([ok({"concepts": []}), ok({"concepts": []})], [])
        lecture = self.make_lecture()

        self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, NO_CONCEPTS)
        self.assertFalse(any(c["schema_name"] == "questions" for c in self.model.calls))

    def test_short_section_gets_one_replacement_round(self):
        self.model = FakeModel(
            two_concepts(),
            [
                mixed_reply("c1", [0], [1, 2, 3]),
                questions_reply("c2", range(4, 8)),
                questions_reply("c1", [8, 9]),
            ],
        )
        lecture = self.make_lecture()

        self.assertTrue(self.run_job(lecture))

        calls = self.section_calls(0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(asked_count(calls[1]), 2)
        self.assertIn(make_question("c1", 0)["prompt"], calls[1]["user_input"])
        self.assertEqual(len(self.section_calls(1)), 1)
        self.assertEqual(lecture.status, "ready")
        self.assertEqual(lecture.questions.count(), 6)

    def test_replacement_round_lists_other_sections_questions(self):
        self.model = FakeModel(
            two_concepts(),
            [
                mixed_reply("c1", [0], [1, 2, 3]),
                questions_reply("c2", range(4, 8)),
                questions_reply("c1", [8, 9]),
            ],
        )
        lecture = self.make_lecture()

        self.assertTrue(self.run_job(lecture))

        text = self.section_calls(0)[1]["user_input"]
        self.assertIn("QUESTIONS FROM OTHER SECTIONS", text)
        self.assertIn(make_question("c2", 4)["prompt"], text)
        self.assertIn("Write exactly 2 questions: 1 easy, 1 medium, 0 hard.", text)

    def test_no_second_replacement_round(self):
        self.model = FakeModel(
            two_concepts(),
            [
                mixed_reply("c1", [0], [1, 2, 3]),
                questions_reply("c2", range(4, 8)),
                mixed_reply("c1", [], [8, 9]),
            ],
        )
        lecture = self.make_lecture()

        self.assertTrue(self.run_job(lecture))

        self.assertEqual(len(self.section_calls(0)), 2)
        self.assertEqual(self.gotcha_calls(), [])
        self.assertEqual(lecture.questions.count(), 5)
        self.assertEqual(lecture.notice, "")

    def short_after_replacement(self, gotchas):
        """Three usable questions after the replacement round, then the given gotcha reply."""
        return FakeModel(
            two_concepts(),
            [
                mixed_reply("c1", [0], [1, 2, 3]),
                mixed_reply("c2", [4, 5], [6, 7]),
                mixed_reply("c1", [], [8, 9]),
                mixed_reply("c2", [], [10]),
                gotchas,
            ],
        )

    def test_gotcha_pass_fills_gap(self):
        self.model = self.short_after_replacement(gotcha_reply("c1", [11, 12, 13]))
        lecture = self.make_lecture()

        with self.assertLogs("quizzes", "INFO") as logs:
            self.assertTrue(self.run_job(lecture))

        self.assertEqual(len(self.gotcha_calls()), 1)
        self.assertEqual(self.gotcha_calls()[0]["effort"], "medium")
        self.assertEqual(lecture.status, "ready")
        self.assertEqual(lecture.notice, "")
        questions = list(lecture.questions.all())
        self.assertEqual(len(questions), 6)
        self.assertEqual(sum(q.generation["gotcha"] is True for q in questions), 3)
        self.assertTrue(any("gotchas=3" in line for line in logs.output))

    def test_gotcha_drafts_are_always_tagged(self):
        # n=30 has the same concept, pattern, and difficulty as the accepted n=0.
        untagged = ok(question_payload(
            *[make_question("c1", n, gotcha=False) for n in (30, 40, 50)]
        ))
        self.model = self.short_after_replacement(untagged)
        lecture = self.make_lecture()

        self.assertTrue(self.run_job(lecture))

        questions = list(lecture.questions.all())
        self.assertEqual(len(questions), 6)
        gotchas = [q for q in questions if q.generation["gotcha"] is True]
        self.assertEqual(len(gotchas), 3)
        self.assertIn(make_question("c1", 30)["prompt"], [q.prompt for q in gotchas])

    def test_gotcha_pass_asks_for_gap_to_target(self):
        self.model = self.short_after_replacement(gotcha_reply("c1", [11, 12, 13]))
        lecture = self.make_lecture()

        self.run_job(lecture)

        call = self.gotcha_calls()[0]
        self.assertEqual(asked_count(call), 3)
        self.assertIn(make_question("c2", 4)["prompt"], call["user_input"])
        self.assertIn(lecture.transcript, call["user_input"])

    def test_short_set_saves_with_notice(self):
        self.model = self.short_after_replacement(ok(question_payload()))
        lecture = self.make_lecture()

        with self.assertLogs("quizzes", "WARNING") as logs:
            self.assertTrue(self.run_job(lecture))

        self.assertEqual(lecture.status, "ready")
        self.assertEqual(
            lecture.notice, "Generated 3 questions (target 6). Add more in review if needed."
        )
        self.assertEqual(lecture.questions.count(), 3)
        self.assertTrue(any(line.startswith("WARNING") for line in logs.output))

    def test_under_floor_fails(self):
        self.model = FakeModel(
            two_concepts(),
            [
                mixed_reply("c1", [0], [1, 2, 3]),
                mixed_reply("c2", [], [4, 5, 6, 7]),
                mixed_reply("c1", [], [8, 9]),
                mixed_reply("c2", [], [10, 11, 12]),
                ok(question_payload()),
            ],
        )
        lecture = self.make_lecture()
        values = {
            "prompt": "Old draft?", "choices": ["r", "w1", "w2", "w3"],
            "correct_index": 0, "difficulty": "easy",
        }
        old = Question.objects.create(
            lecture=lecture, generation={"original": original_of(**values)}, **values
        )

        self.assertFalse(self.run_job(lecture))

        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, "Only 1 usable questions were made. Try again.")
        self.assertEqual(list(lecture.questions.values_list("id", flat=True)), [old.id])

    def test_kept_drop_during_skip_uses_short_notice(self):
        lecture = self.make_lecture()
        for n in range(6):
            Question.objects.create(
                lecture=lecture, position=n, prompt=f"Hand question {n}?",
                choices=[f"r{n}", f"w{n}a", f"w{n}b", f"w{n}c"], correct_index=0,
                difficulty="easy",
            )
        self.model = FakeModel([], [])

        def delete_some(lecture_id, token, message):
            if message == "Saving questions":
                Question.objects.filter(pk__in=list(
                    lecture.questions.values_list("pk", flat=True)[:3]
                )).delete()
            real_heartbeat(lecture_id, token, message)

        with mock.patch("quizzes.question_generation.heartbeat", side_effect=delete_some):
            self.assertTrue(self.run_job(lecture))

        self.assertEqual(self.model.calls, [])
        self.assertEqual(
            lecture.notice, "Generated 3 questions (target 6). Add more in review if needed."
        )

    @override_settings(QUESTION_MAX_COST_USD=0.0001)
    def test_cost_cap_stops_before_call(self):
        self.model = FakeModel(two_concepts(), [])
        lecture = self.make_lecture()

        self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, QUESTIONS_TOO_EXPENSIVE)
        self.assertEqual(self.model.calls, [])

    @override_settings(QUESTION_MAX_COST_USD=0.01)
    def test_cost_cap_counts_real_usage(self):
        self.model = FakeModel(
            [ok(concept_payload("Alpha"), output=30_000), ok(concept_payload("Beta"))], []
        )
        lecture = self.make_lecture()

        self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, QUESTIONS_TOO_EXPENSIVE)
        self.assertEqual(len(self.model.calls), 1)

    @override_settings(QUESTION_MAX_COST_USD=0.01)
    def test_cost_of_bad_reply_blocks_reask(self):
        expensive_bad = Reply(None, Usage(1000, 0, 30_000), "bad_json")
        self.model = FakeModel([expensive_bad, *two_concepts()], [])
        lecture = self.make_lecture()

        self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, QUESTIONS_TOO_EXPENSIVE)
        self.assertEqual(len(self.model.calls), 1)

    def test_permanent_client_error_fails(self):
        self.model = raising(PermanentError(QUESTIONS_BAD_KEY))
        lecture = self.make_lecture()

        self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, QUESTIONS_BAD_KEY)

    def test_transient_error_raises(self):
        self.model = raising(TransientError(QUESTIONS_BUSY))
        lecture = self.make_lecture()

        with self.assertRaises(TransientError):
            self.run_job(lecture)

        lecture.refresh_from_db()
        self.assertEqual(lecture.status, "processing")
        self.assertEqual(lecture.job_token, TOKEN)

    def test_soft_time_limit_fails(self):
        self.model = raising(SoftTimeLimitExceeded())
        lecture = self.make_lecture()

        self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, TIMEOUT)

    def test_unexpected_error_fails(self):
        self.model = raising(ValueError("boom"))
        lecture = self.make_lecture()

        with self.assertLogs("quizzes", "ERROR") as logs:
            self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, UNEXPECTED)
        self.assertTrue(any(line.startswith("ERROR") for line in logs.output))

    def test_lost_ownership_before_reask_makes_no_second_call(self):
        lecture = self.make_lecture()
        calls = []

        def model(**kwargs):
            calls.append(kwargs)
            Lecture.objects.filter(pk=lecture.id).update(job_token="other")
            return bad("bad_json")

        self.model = model

        self.assertFalse(self.run_job(lecture))

        self.assertEqual(len(calls), 1)
        self.assertEqual(lecture.job_token, "other")

    def test_redelivered_message_fails_without_a_call(self):
        self.model = default_model()
        lecture = self.make_lecture(job_token=TOKEN)

        with self.assertLogs("quizzes", "WARNING") as logs:
            self.assertFalse(self.run_job(lecture))

        self.assert_failed(lecture, INTERRUPTED)
        self.assertEqual(self.model.calls, [])
        self.assertTrue(any("redelivered message" in line for line in logs.output))

    def test_retry_claims_its_own_token(self):
        self.model = default_model()
        lecture = self.make_lecture(job_token=TOKEN)

        from quizzes.question_generation import run_question_generation

        log = job_logger(lecture.id, TOKEN, 1)
        self.assertTrue(run_question_generation(lecture.id, TOKEN, 1, log))
        lecture.refresh_from_db()
        self.assertEqual(lecture.status, "ready")

    def test_lock_busy_is_transient(self):
        self.model = FakeModel(two_concepts(), [])
        lecture = self.make_lecture()

        with mock.patch("quizzes.question_generation.lecture_lock", busy_lock):
            with self.assertRaises(TransientError):
                self.run_job(lecture)

        self.assertEqual(self.model.calls, [])


def lopsided_question(concept_id, n, **over):
    """A valid question whose correct answer is far longer than every wrong choice."""
    return make_question(
        concept_id,
        n,
        choices=[f"A much longer and fuller true claim {n}", f"No {n}a", f"No {n}b", f"No {n}c"],
        **over,
    )


def distractor_reply(*items):
    return ok({"distractors": list(items)})


def rewrite(index, n, texts=None, types=None):
    return {
        "index": index,
        "distractors": texts or [
            f"A much longer and fuller false claim {n}a",
            f"A much longer and fuller false claim {n}b",
            f"A much longer and fuller false claim {n}c",
        ],
        "distractor_types": types or ["neighbor_step", "overly_absolute", "opposite_effect"],
    }


@override_settings(
    QUESTION_WORDS_PER_QUESTION=100,
    QUESTION_MIN_COUNT=4,
    QUESTION_MAX_COUNT=8,
    QUESTION_FLOOR_COUNT=2,
    QUESTION_MAX_COST_USD=0.25,
    QUESTION_MODEL="gpt-6-luna",
)
class LopsidedRewriteTests(QuestionJobMixin, TestCase):
    """Target is 6 and each section is asked for 3, so 3 per reply means nothing is trimmed."""

    def model_with(self, c1_questions, distractors=()):
        return FakeModel(
            two_concepts(),
            [ok(question_payload(*c1_questions)), questions_reply("c2", range(4, 7))],
            distractors,
        )

    def distractor_calls(self):
        return [call for call in self.model.calls if call["schema_name"] == "distractors"]

    def listed(self, call):
        return json.loads(call["user_input"])

    def saved(self, lecture, n):
        prompt = make_question("c1", n)["prompt"]
        return lecture.questions.get(prompt=prompt)

    def run_and_capture(self, lecture):
        """Run the job and return the drafts as they reached balance_positions."""
        seen = []

        def capture(drafts, seed):
            seen.extend(copy.deepcopy(drafts))
            return real_balance(drafts, seed)

        with mock.patch("quizzes.question_generation.balance_positions", side_effect=capture):
            with self.assertLogs("quizzes", "INFO") as logs:
                self.assertTrue(self.run_job(lecture))
        return seen, logs.output

    def summary(self, logs):
        return [line for line in logs if "cost_usd=" in line][0]

    def test_no_lopsided_drafts_make_no_call(self):
        self.model = self.model_with([make_question("c1", n) for n in range(3)])
        lecture = self.make_lecture()

        with self.assertLogs("quizzes", "INFO") as logs:
            self.assertTrue(self.run_job(lecture))

        self.assertEqual(self.distractor_calls(), [])
        summary = self.summary(logs.output)
        self.assertIn("rebalanced=0 still_lopsided=0 longest_correct_pct=0", summary)

    def test_lopsided_drafts_get_one_call_listing_only_them(self):
        self.model = self.model_with(
            [lopsided_question("c1", 0), make_question("c1", 1), lopsided_question("c1", 2)],
            [distractor_reply()],
        )
        lecture = self.make_lecture()

        with mock.patch("quizzes.question_generation.heartbeat", wraps=real_heartbeat) as beat:
            self.assertTrue(self.run_job(lecture))

        calls = self.distractor_calls()
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["schema"], DISTRACTOR_SCHEMA)
        self.assertEqual(call["instructions"], DISTRACTOR_INSTRUCTIONS)
        self.assertEqual(call["effort"], "medium")
        self.assertEqual(call["max_output_tokens"], 8000)
        listed = self.listed(call)
        self.assertEqual(
            [item["prompt"] for item in listed],
            [make_question("c1", 0)["prompt"], make_question("c1", 2)["prompt"]],
        )
        self.assertEqual([item["index"] for item in listed], [1, 2])
        first = listed[0]
        self.assertEqual(first["correct_answer"], "A much longer and fuller true claim 0")
        self.assertEqual(first["wrong_choices"], ["No 0a", "No 0b", "No 0c"])
        self.assertEqual(first["concept"], "Alpha")
        self.assertEqual(first["concept_summary"], "What Alpha is.")
        messages = [c.args[2] for c in beat.call_args_list]
        self.assertIn("Balancing answer choices", messages)
        self.assertLess(
            messages.index("Balancing answer choices"), messages.index("Saving questions")
        )

    def test_not_except_drafts_are_never_sent(self):
        self.model = self.model_with(
            [
                lopsided_question("c1", 0, pattern="not_except"),
                lopsided_question("c1", 1),
                make_question("c1", 2),
            ],
            [distractor_reply()],
        )
        lecture = self.make_lecture()

        with self.assertLogs("quizzes", "INFO") as logs:
            self.assertTrue(self.run_job(lecture))

        calls = self.distractor_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            [item["prompt"] for item in self.listed(calls[0])], [make_question("c1", 1)["prompt"]]
        )
        self.assertIn("rebalanced=0 still_lopsided=2", self.summary(logs.output))

    def test_only_not_except_lopsided_makes_no_call(self):
        self.model = self.model_with(
            [
                lopsided_question("c1", 0, pattern="not_except"),
                make_question("c1", 1),
                make_question("c1", 2),
            ],
        )
        lecture = self.make_lecture()

        with self.assertLogs("quizzes", "INFO") as logs:
            self.assertTrue(self.run_job(lecture))

        self.assertEqual(self.distractor_calls(), [])
        self.assertIn("rebalanced=0 still_lopsided=1", self.summary(logs.output))

    def test_valid_rewrite_replaces_distractors_before_balancing(self):
        self.model = self.model_with(
            [make_question("c1", 0), lopsided_question("c1", 1, correct_index=0), make_question("c1", 2)],
            [distractor_reply(rewrite(1, 1))],
        )
        lecture = self.make_lecture()

        seen, logs = self.run_and_capture(lecture)

        draft = [d for d in seen if d.prompt == make_question("c1", 1)["prompt"]][0]
        self.assertEqual(draft.correct_index, 0)
        self.assertEqual(
            draft.choices,
            [
                "A much longer and fuller true claim 1",
                "A much longer and fuller false claim 1a",
                "A much longer and fuller false claim 1b",
                "A much longer and fuller false claim 1c",
            ],
        )
        self.assertEqual(
            draft.distractor_types, [None, "neighbor_step", "overly_absolute", "opposite_effect"]
        )
        question = self.saved(lecture, 1)
        self.assertEqual(question.choices[question.correct_index], "A much longer and fuller true claim 1")
        self.assertIn("A much longer and fuller false claim 1b", question.choices)
        self.assertIsNone(question.generation["distractor_types"][question.correct_index])
        self.assertEqual(question.generation["original"]["choices"], question.choices)
        self.assertIn("rebalanced=1 still_lopsided=0", self.summary(logs))

    def test_rewrite_keeps_correct_answer_at_its_index(self):
        self.model = self.model_with(
            [make_question(
                "c1", 0, correct_index=2,
                choices=["No 0a", "No 0b", "A much longer and fuller true claim 0", "No 0c"],
                distractor_types=["wrong_mechanism", "opposite_effect", None, "generic_benefit"],
            ), make_question("c1", 1), make_question("c1", 2)],
            [distractor_reply(rewrite(1, 0))],
        )
        lecture = self.make_lecture()

        seen, _ = self.run_and_capture(lecture)

        draft = [d for d in seen if d.prompt == make_question("c1", 0)["prompt"]][0]
        self.assertEqual(draft.correct_index, 2)
        self.assertEqual(draft.choices[2], "A much longer and fuller true claim 0")
        self.assertEqual(draft.choices[0], "A much longer and fuller false claim 0a")
        self.assertEqual(draft.choices[3], "A much longer and fuller false claim 0c")
        self.assertEqual(
            draft.distractor_types, ["neighbor_step", "overly_absolute", None, "opposite_effect"]
        )

    def test_rewrite_that_fails_checks_keeps_original(self):
        bad_texts = ["A much longer and fuller true claim 0", "Other wrong 0b", "Other wrong 0c"]
        self.model = self.model_with(
            [lopsided_question("c1", 0), make_question("c1", 1), make_question("c1", 2)],
            [distractor_reply(rewrite(1, 0, texts=bad_texts))],
        )
        lecture = self.make_lecture()

        seen, logs = self.run_and_capture(lecture)

        draft = [d for d in seen if d.prompt == make_question("c1", 0)["prompt"]][0]
        self.assertEqual(
            sorted(draft.choices),
            sorted(["A much longer and fuller true claim 0", "No 0a", "No 0b", "No 0c"]),
        )
        self.assertTrue(any("rewrite rejected reason=duplicate_choices" in line for line in logs))
        self.assertIn("rebalanced=0 still_lopsided=1", self.summary(logs))

    def test_still_lopsided_rewrite_is_kept_and_counted(self):
        short = ["Nope 0a", "Nope 0b", "Nope 0c"]
        self.model = self.model_with(
            [lopsided_question("c1", 0), make_question("c1", 1), make_question("c1", 2)],
            [distractor_reply(rewrite(1, 0, texts=short))],
        )
        lecture = self.make_lecture()

        seen, logs = self.run_and_capture(lecture)

        draft = [d for d in seen if d.prompt == make_question("c1", 0)["prompt"]][0]
        self.assertEqual(draft.choices[1:], short)
        self.assertTrue(any("still_lopsided=1" in line and "cost_usd=" not in line for line in logs))
        self.assertIn("rebalanced=1 still_lopsided=1", self.summary(logs))
        self.assertEqual(lecture.questions.count(), 6)

    def test_unknown_and_duplicate_indexes_are_ignored(self):
        self.model = self.model_with(
            [lopsided_question("c1", 0), make_question("c1", 1), make_question("c1", 2)],
            [distractor_reply(rewrite(7, 0), rewrite(1, 0), rewrite(1, 9))],
        )
        lecture = self.make_lecture()

        seen, logs = self.run_and_capture(lecture)

        draft = [d for d in seen if d.prompt == make_question("c1", 0)["prompt"]][0]
        self.assertEqual(draft.choices[1], "A much longer and fuller false claim 0a")
        self.assertIn("rebalanced=1 still_lopsided=0", self.summary(logs))

    def test_two_bad_replies_keep_originals_and_save(self):
        self.model = self.model_with(
            [lopsided_question("c1", 0), make_question("c1", 1), make_question("c1", 2)],
            [bad("bad_json"), bad("incomplete")],
        )
        lecture = self.make_lecture()

        seen, logs = self.run_and_capture(lecture)

        self.assertEqual(lecture.status, "ready")
        self.assertEqual(len(self.distractor_calls()), 2)
        question = self.saved(lecture, 0)
        self.assertEqual(
            sorted(question.choices),
            sorted(["A much longer and fuller true claim 0", "No 0a", "No 0b", "No 0c"]),
        )
        self.assertTrue(any("WARNING" in line and "rewrite skipped" in line for line in logs))
        self.assertIn("rebalanced=0 still_lopsided=1", self.summary(logs))

    def test_cost_cap_on_rewrite_keeps_originals_and_saves(self):
        self.model = self.model_with(
            [lopsided_question("c1", 0), make_question("c1", 1), make_question("c1", 2)],
        )
        lecture = self.make_lecture()

        def estimate(chars, max_output_tokens, model):
            return 1.0 if max_output_tokens == 8000 else 0.0

        with mock.patch("quizzes.question_generation.estimate_cost", side_effect=estimate):
            seen, logs = self.run_and_capture(lecture)

        self.assertEqual(lecture.status, "ready")
        self.assertEqual(self.distractor_calls(), [])
        self.assertEqual(lecture.questions.count(), 6)
        self.assertTrue(any("rewrite skipped" in line for line in logs))
        self.assertIn("rebalanced=0 still_lopsided=1", self.summary(logs))

    def test_other_errors_on_rewrite_fail_the_lecture(self):
        script = self.model_with(
            [lopsided_question("c1", 0), make_question("c1", 1), make_question("c1", 2)],
        )

        def model(**kwargs):
            if kwargs["schema_name"] == "distractors":
                raise PermanentError(QUESTIONS_BAD_KEY)
            return script(**kwargs)

        self.model = model
        lecture = self.make_lecture()

        self.assertFalse(self.run_job(lecture))

        self.assertEqual(lecture.status, "failed")
        self.assertEqual(lecture.error_message, QUESTIONS_BAD_KEY)

    def test_kept_questions_are_never_sent(self):
        Question.objects.create(
            lecture=self.make_lecture(),
            position=0,
            prompt="Kept lopsided question?",
            choices=["A much longer and fuller kept answer", "No a", "No b", "No c"],
            correct_index=0,
            difficulty="easy",
        )
        lecture = Lecture.objects.get()
        self.model = FakeModel(
            two_concepts(),
            [
                ok(question_payload(*[lopsided_question("c1", n) for n in range(3)])),
                questions_reply("c2", range(4, 7)),
            ],
            [distractor_reply()],
        )

        self.assertTrue(self.run_job(lecture))

        calls = self.distractor_calls()
        self.assertEqual(len(calls), 1)
        self.assertNotIn("Kept lopsided question?", calls[0]["user_input"])
        self.assertNotIn("kept answer", calls[0]["user_input"])
        self.assertTrue(lecture.questions.filter(prompt="Kept lopsided question?").exists())

    def test_summary_reports_longest_correct_percent(self):
        self.model = self.model_with(
            [lopsided_question("c1", 0), make_question("c1", 1), make_question("c1", 2)],
            [distractor_reply()],
        )
        lecture = self.make_lecture()

        with self.assertLogs("quizzes", "INFO") as logs:
            self.assertTrue(self.run_job(lecture))

        summary = self.summary(logs.output)
        self.assertIn("longest_correct=1/6", summary)
        self.assertIn("longest_correct_pct=17", summary)
        self.assertIn("rebalanced=0 still_lopsided=1", summary)
