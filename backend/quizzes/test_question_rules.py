from django.test import SimpleTestCase, override_settings

from .question_prompts import (
    CONCEPT_INSTRUCTIONS,
    CONCEPT_SCHEMA,
    QUESTION_INSTRUCTIONS,
    QUESTION_SCHEMA,
)
from .question_rules import Section, merge_concepts, split_sections, target_count


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
