from django.test import SimpleTestCase, override_settings

from .question_prompts import (
    CONCEPT_INSTRUCTIONS,
    CONCEPT_SCHEMA,
    QUESTION_INSTRUCTIONS,
    QUESTION_SCHEMA,
)
from .question_rules import (
    Draft,
    QuestionSet,
    Section,
    check_draft,
    merge_concepts,
    section_quotas,
    soft_flags,
    split_sections,
    target_count,
)


def _object_nodes(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for value in node.values():
            yield from _object_nodes(value)
    elif isinstance(node, list):
        for value in node:
            yield from _object_nodes(value)


def _question_item():
    return QUESTION_SCHEMA["properties"]["questions"]["items"]


class SchemaTests(SimpleTestCase):
    def test_schemas_are_strict(self):
        for schema in (CONCEPT_SCHEMA, QUESTION_SCHEMA):
            nodes = list(_object_nodes(schema))
            self.assertGreaterEqual(len(nodes), 2)
            for node in nodes:
                self.assertIs(node["additionalProperties"], False)
                self.assertEqual(set(node["required"]), set(node["properties"]))

    def test_question_schema_enums(self):
        item = _question_item()["properties"]
        self.assertEqual(
            tuple(item["pattern"]["enum"]),
            (
                "purpose",
                "mechanism",
                "consequence",
                "choose_method",
                "completion",
                "comparison",
                "tradeoff",
                "not_except",
                "fill_blank",
                "read_example",
            ),
        )
        self.assertEqual(item["difficulty"]["enum"], ["easy", "medium", "hard"])
        self.assertEqual(
            set(item["distractor_types"]["items"]["enum"]),
            {
                "wrong_mechanism",
                "opposite_effect",
                "generic_benefit",
                "overly_absolute",
                "neighbor_step",
                None,
            },
        )
        self.assertEqual(item["choices"]["minItems"], 4)
        self.assertEqual(item["choices"]["maxItems"], 4)


class InstructionTests(SimpleTestCase):
    def test_instructions_carry_the_rules(self):
        self.assertIn("never mention the professor", QUESTION_INSTRUCTIONS)
        self.assertIn("all of the above", QUESTION_INSTRUCTIONS)
        self.assertIn("EXCEPT", QUESTION_INSTRUCTIONS)
        self.assertIn("30/50/20", QUESTION_INSTRUCTIONS)
        self.assertIn("logistics", CONCEPT_INSTRUCTIONS)
        self.assertIn("stories", CONCEPT_INSTRUCTIONS)


class TargetCountTests(SimpleTestCase):
    @override_settings(
        QUESTION_WORDS_PER_QUESTION=300, QUESTION_MIN_COUNT=20, QUESTION_MAX_COUNT=40
    )
    def test_target_count(self):
        self.assertEqual(target_count(8966), 30)
        self.assertEqual(target_count(1000), 20)
        self.assertEqual(target_count(20000), 40)


class SplitSectionsTests(SimpleTestCase):
    def test_split_uses_raw_chunks(self):
        raw = {
            "chunks": [
                {"index": 0, "start": 0, "end": 600, "text": "a b"},
                {"index": 1, "start": 598, "end": 1226, "text": "c"},
            ]
        }
        sections = split_sections("ignored", raw)
        self.assertEqual(
            sections,
            [Section(0, 0, 600, "a b"), Section(1, 598, 1226, "c")],
        )
        self.assertEqual(sections[0].words, 2)

    def test_split_falls_back_to_plain_text(self):
        sentence = "one two three four five six seven eight nine ten."
        transcript = " ".join([sentence] * 270)
        sections = split_sections(transcript, None)
        self.assertIn(len(sections), (2, 3))
        for position, section in enumerate(sections):
            self.assertEqual(section.index, position)
            self.assertIsNone(section.start)
            self.assertIsNone(section.end)
            self.assertTrue(section.text.endswith("."))
        joined = " ".join(section.text for section in sections)
        self.assertEqual(joined.split(), transcript.split())

    def test_split_skips_empty_chunk_text(self):
        raw = {
            "chunks": [
                {"index": 0, "start": 0, "end": 600, "text": "first part"},
                {"index": 1, "start": 598, "end": 1200, "text": "  "},
                {"index": 2, "start": 1198, "end": 1800, "text": "third part"},
            ]
        }
        sections = split_sections("ignored", raw)
        self.assertEqual([section.index for section in sections], [0, 2])
        self.assertEqual(sections[1].text, "third part")


def _concept(name):
    return {"name": name, "summary": f"About {name}."}


class MergeConceptsTests(SimpleTestCase):
    def test_merge_concepts_dedupes_across_sections(self):
        concepts = merge_concepts(
            [
                (0, [_concept("Race condition")]),
                (1, [_concept("race conditions"), _concept("Mutex")]),
            ]
        )
        self.assertEqual(len(concepts), 2)
        self.assertEqual(
            [(c.id, c.name, c.section_index) for c in concepts],
            [("c1", "Race condition", 0), ("c2", "Mutex", 1)],
        )
        self.assertEqual(concepts[0].data["summary"], "About Race condition.")

    def test_merge_keeps_lecture_order(self):
        concepts = merge_concepts(
            [
                (0, [_concept("Thread"), _concept("Process")]),
                (1, [_concept("Deadlock")]),
                (2, [_concept("Semaphore"), _concept("Monitor")]),
            ]
        )
        self.assertEqual(
            [c.name for c in concepts],
            ["Thread", "Process", "Deadlock", "Semaphore", "Monitor"],
        )
        orders = [c.order for c in concepts]
        self.assertEqual(orders, sorted(orders))
        self.assertEqual(len(set(orders)), len(orders))
        self.assertEqual([c.id for c in concepts], ["c1", "c2", "c3", "c4", "c5"])


def raw_q(**over):
    question = {
        "prompt": "Why does a mutex prevent a race condition?",
        "choices": ["It copies data", "It allows one thread at a time", "It adds threads", "It speeds up reads"],
        "correct_index": 1,
        "difficulty": "medium",
        "reason": "A mutex gives exclusive access.",
        "concept_id": "c1",
        "pattern": "mechanism",
        "gotcha": False,
        "distractor_types": [None, None, None, None],
    }
    question.update(over)
    return question


def accepted(**over):
    draft, reason = check_draft(raw_q(**over), {"c1", "c2"}, 2)
    assert draft is not None, reason
    return draft


class CheckDraftTests(SimpleTestCase):
    def reason(self, **over):
        return check_draft(raw_q(**over), {"c1", "c2"}, 2)[1]

    def test_valid_draft_passes(self):
        draft, reason = check_draft(raw_q(), {"c1"}, 2)
        self.assertEqual(reason, "")
        self.assertEqual(draft.section_index, 2)
        self.assertEqual(draft.concept_id, "c1")

    def test_each_reason(self):
        self.assertEqual(self.reason(choices=["a", "b", "c"]), "shape")
        self.assertEqual(self.reason(choices=["a", "  ", "c", "d"]), "blank_choice")
        self.assertEqual(self.reason(correct_index=4), "bad_index")
        self.assertEqual(self.reason(difficulty="expert"), "bad_difficulty")
        self.assertEqual(self.reason(prompt="x" * 501), "too_long")
        self.assertEqual(self.reason(choices=["a", "b", "c", "d" * 201]), "too_long")
        self.assertEqual(self.reason(choices=["a", "b", "c", "None of the above"]), "all_none_above")
        self.assertEqual(self.reason(concept_id="c99"), "unknown_concept")

    def test_drops_duplicate_choices_after_normalizing(self):
        self.assertEqual(self.reason(choices=["Mutex", " mutex ", "b", "c"]), "duplicate_choices")

    def test_drops_speaker_and_logistics(self):
        for prompt in (
            "What did the professor say about X?",
            "According to the instructor, why does a mutex help?",
            "What did the speaker mention about locks?",
            "When is the homework due?",
            "How is grading weighted?",
        ):
            self.assertEqual(self.reason(prompt=prompt), "speaker_or_logistics", prompt)

    def test_keeps_soft_phrases(self):
        for prompt in (
            "Which statement about this lecture's sorting example is correct?",
            "As said earlier, a mutex gives what guarantee?",
        ):
            draft, reason = check_draft(raw_q(prompt=prompt), {"c1"}, 0)
            self.assertEqual(reason, "", prompt)
            self.assertTrue(soft_flags(draft), prompt)
        self.assertEqual(soft_flags(accepted()), [])

    def test_word_boundaries(self):
        self.assertEqual(self.reason(prompt="What does the gradient measure?"), "")
        self.assertEqual(self.reason(prompt="Which data is undue to cache?"), "")

    def test_drops_choice_references(self):
        for text in (
            "A and B", "Both A and B", "Either A or C", "Neither B nor D",
            "Both of the above", "BOTH OF THE ABOVE", "Options 1 and 3", "Choice C",
        ):
            choices = ["w", "x", "y", text]
            self.assertEqual(self.reason(choices=choices), "choice_reference", text)

    def test_keeps_lowercase_letter_text(self):
        for text in ("Answer a query from the cache", "Pick option a from the menu", "a and b are swapped"):
            self.assertEqual(self.reason(choices=["w", "x", "y", text]), "", text)

    def test_check_order_prefers_shape_first(self):
        self.assertEqual(self.reason(choices=["a"], correct_index=9), "shape")


class QuestionSetTests(SimpleTestCase):
    def test_near_duplicate(self):
        questions = QuestionSet([])
        self.assertEqual(questions.add(accepted()), "")
        near = accepted(prompt="Why does a mutex prevent a race condition today?", difficulty="hard")
        self.assertEqual(questions.add(near), "near_duplicate")
        self.assertEqual(len(questions.new), 1)

    def test_grid_same_difficulty_full(self):
        questions = QuestionSet([])
        questions.add(accepted())
        other = accepted(
            prompt="Which statement describes semaphores?",
            choices=["p", "q", "r", "s"],
        )
        self.assertEqual(questions.add(other), "grid_full")

    def test_grid_allows_other_difficulty(self):
        questions = QuestionSet([])
        questions.add(accepted())
        other = accepted(prompt="Which statement describes semaphores?", choices=["p", "q", "r", "s"], difficulty="hard")
        self.assertEqual(questions.add(other), "")

    def test_grid_exempts_gotcha(self):
        questions = QuestionSet([])
        questions.add(accepted())
        other = accepted(prompt="Which statement describes semaphores?", choices=["p", "q", "r", "s"], gotcha=True)
        self.assertEqual(questions.add(other), "")

    def test_kept_questions_block_duplicates(self):
        kept = accepted()
        questions = QuestionSet([kept])
        near = accepted(prompt="Why does a mutex prevent a race condition today?", difficulty="hard")
        self.assertEqual(questions.add(near), "near_duplicate")
        self.assertEqual(questions.new, [])

    def test_kept_questions_fill_grid_cells(self):
        questions = QuestionSet([accepted()])
        other = accepted(prompt="Which statement describes semaphores?", choices=["p", "q", "r", "s"])
        self.assertEqual(questions.add(other), "grid_full")

    def test_kept_without_concept_checks_duplicates_only(self):
        kept = Draft(
            prompt="Why does a mutex prevent a race condition?",
            choices=["It copies data", "It allows one thread at a time", "It adds threads", "It speeds up reads"],
            correct_index=1, difficulty="medium", reason="", concept_id="", pattern="",
            gotcha=False, distractor_types=[None] * 4, section_index=-1,
        )
        questions = QuestionSet([kept])
        self.assertEqual(questions.add(accepted()), "near_duplicate")
        other = accepted(prompt="Which statement describes semaphores?", choices=["p", "q", "r", "s"])
        self.assertEqual(questions.add(other), "")


class SectionQuotaTests(SimpleTestCase):
    def sections(self, *sizes):
        return [Section(i, None, None, " ".join(["w"] * n)) for i, n in enumerate(sizes)]

    def test_quotas_follow_word_share(self):
        quotas = section_quotas(10, self.sections(1300, 1300, 650), {0, 1, 2})
        self.assertEqual(quotas, {0: 4, 1: 4, 2: 2})

    def test_quotas_skip_sections_without_concepts(self):
        quotas = section_quotas(10, self.sections(1300, 1300, 650), {0, 2})
        self.assertEqual(quotas[1], 0)
        self.assertEqual(sum(quotas.values()), 10)

    def test_quotas_use_largest_remainder(self):
        quotas = section_quotas(5, self.sections(100, 100, 100), {0, 1, 2})
        self.assertEqual(quotas, {0: 2, 1: 2, 2: 1})

    def test_quotas_empty_when_no_concepts(self):
        self.assertEqual(section_quotas(5, self.sections(100, 100), set()), {0: 0, 1: 0})
