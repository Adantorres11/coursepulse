from django.test import SimpleTestCase, override_settings

from .question_prompts import (
    CONCEPT_INSTRUCTIONS,
    CONCEPT_SCHEMA,
    GOTCHA_INSTRUCTIONS,
    QUESTION_INSTRUCTIONS,
    QUESTION_SCHEMA,
)
from .question_rules import (
    Concept,
    Draft,
    QuestionSet,
    Section,
    balance_positions,
    check_draft,
    concept_ids_for,
    difficulty_split,
    is_untouched,
    merge_concepts,
    mix_warnings,
    order_drafts,
    original_of,
    section_quotas,
    soft_flags,
    split_sections,
    target_count,
    trim,
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

    def test_both_question_instructions_carry_the_wording_rules(self):
        for instructions in (QUESTION_INSTRUCTIONS, GOTCHA_INSTRUCTIONS):
            with self.subTest(instructions=instructions[:30]):
                self.assertIn("about the same length", instructions)
                self.assertIn("as long and as specific as the correct answer", instructions)
                self.assertIn("only long, detailed, or hedged choice", instructions)
                self.assertIn("must stand alone", instructions)
                self.assertIn("'described', 'stated'", instructions)
                self.assertIn("connecting two or more ideas", instructions)

    def test_question_instructions_ask_for_exact_counts_and_no_repeats(self):
        self.assertIn("exact counts", QUESTION_INSTRUCTIONS)
        self.assertIn("same idea as any listed existing question", QUESTION_INSTRUCTIONS)
        self.assertIn("even if it is about a different concept", QUESTION_INSTRUCTIONS)

    def test_concept_instructions_skip_example_products(self):
        self.assertIn("example products", CONCEPT_INSTRUCTIONS)
        self.assertIn("extract that general idea", CONCEPT_INSTRUCTIONS)


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

    def test_split_cuts_unpunctuated_text_by_words(self):
        words = [f"w{i}" for i in range(3000)]
        sections = split_sections(" ".join(words), None)
        self.assertGreater(len(sections), 1)
        self.assertTrue(all(section.words <= 1300 * 1.5 for section in sections))
        joined = " ".join(section.text for section in sections)
        self.assertEqual(joined.split(), words)

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

    def test_concept_ids_for_maps_names_to_merged_ids(self):
        concepts = merge_concepts(
            [
                (0, [_concept("Race condition"), _concept("Thread")]),
                (1, [_concept("race conditions"), _concept("Mutex")]),
            ]
        )
        self.assertEqual(
            concept_ids_for(["race conditions", "Mutex", "Mutex", "", "Scheduler"], concepts),
            ["c1", "c3"],
        )


    def test_merge_keeps_neighbor_concepts_apart(self):
        pairs = [
            ("Type I error", "Type II error"),
            ("Pre-order traversal", "Post-order traversal"),
            ("Big-O notation", "Big-Omega notation"),
            ("Layer 2", "Layer 3"),
            ("IPv4 address", "IPv6 address"),
        ]
        for first, second in pairs:
            with self.subTest(first=first, second=second):
                concepts = merge_concepts([(0, [_concept(first)]), (1, [_concept(second)])])
                self.assertEqual([c.name for c in concepts], [first, second])
                self.assertEqual(concept_ids_for([second], concepts), ["c2"])

    def test_merge_joins_plural_forms(self):
        concepts = merge_concepts(
            [(0, [_concept("Race condition"), _concept("Mutex")]),
             (1, [_concept("race conditions"), _concept("mutexes")])]
        )
        self.assertEqual([c.name for c in concepts], ["Race condition", "Mutex"])
        self.assertEqual(concept_ids_for(["mutexes", "race conditions"], concepts), ["c2", "c1"])

    def test_merge_keeps_same_section_names_apart(self):
        concepts = merge_concepts([(0, [_concept("Mutex"), _concept("Mutexes")])])
        self.assertEqual([c.name for c in concepts], ["Mutex", "Mutexes"])

    def test_concept_ids_for_prefers_exact_match(self):
        concepts = merge_concepts([(0, [_concept("Mutex"), _concept("Mutexes")])])
        self.assertEqual(concept_ids_for(["Mutexes"], concepts), ["c2"])


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

    def test_code_style_choices_stay_distinct(self):
        for choices in (["C++", "C", "C#", "Java"], ["[]", "{}", "()", "<>"]):
            self.assertEqual(self.reason(choices=choices), "", choices)

    def test_trailing_sentence_punctuation_is_ignored(self):
        self.assertEqual(self.reason(choices=["Mutex.", "mutex", "b", "c"]), "duplicate_choices")

    def test_hard_drop_phrase_must_sit_in_one_text(self):
        choices = ["It said nothing", "It returned 0", "It crashed", "It hung"]
        self.assertEqual(self.reason(prompt="What did the kernel return?", choices=choices), "")
        self.assertEqual(
            self.reason(prompt="What did the professor say about locks?"), "speaker_or_logistics"
        )

    def test_drops_each_logistics_word(self):
        for word in ("due date", "midterm", "final exam", "attendance", "syllabus", "office hours", "extra credit"):
            self.assertEqual(
                self.reason(prompt=f"What is the {word} for this course?"), "speaker_or_logistics", word
            )

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

    def test_same_answer_under_other_concept_is_not_duplicate(self):
        questions = QuestionSet([])
        questions.add(accepted())
        self.assertEqual(questions.add(accepted(concept_id="c2")), "")

    def test_gotcha_does_not_occupy_a_cell(self):
        questions = QuestionSet([])
        self.assertEqual(questions.add(accepted(gotcha=True)), "")
        other = accepted(prompt="Which statement describes semaphores?", choices=["p", "q", "r", "s"])
        self.assertEqual(questions.add(other), "")

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


def make_draft(prompt="Q?", correct_index=0, difficulty="medium", concept_id="c1", section_index=0, choices=None):
    return Draft(
        prompt=prompt,
        choices=choices or ["a1", "b2", "c3", "d4"],
        correct_index=correct_index,
        difficulty=difficulty,
        reason="",
        concept_id=concept_id,
        pattern="purpose",
        gotcha=False,
        distractor_types=[None, "wrong_mechanism", "opposite_effect", "generic_benefit"],
        section_index=section_index,
    )


class TrimTests(SimpleTestCase):
    def test_trim_noop_when_under(self):
        drafts = [make_draft(f"q{i}") for i in range(5)]
        self.assertEqual(trim(drafts, 6, {0: 5}), drafts)

    def test_trim_removes_from_most_surplus_section_last_first(self):
        drafts = [make_draft(f"s0-{i}", section_index=0) for i in range(4)]
        drafts += [make_draft(f"s1-{i}", section_index=1) for i in range(2)]
        result = trim(drafts, 5, {0: 3, 1: 2})
        self.assertEqual(len(result), 5)
        self.assertNotIn("s0-3", [d.prompt for d in result])
        self.assertEqual(len(drafts), 6)

    def test_trim_tie_takes_higher_section_first(self):
        drafts = [make_draft("a", section_index=0), make_draft("b", section_index=1)]
        self.assertEqual([d.prompt for d in trim(drafts, 1, {0: 0, 1: 0})], ["a"])

    def test_trim_cuts_surplus_not_size(self):
        drafts = [make_draft(f"s0-{i}", section_index=0) for i in range(9)]
        drafts += [make_draft(f"s1-{i}", section_index=1) for i in range(5)]
        drafts += [make_draft(f"s2-{i}", section_index=2) for i in range(5)]
        result = trim(drafts, 16, {0: 8, 1: 4, 2: 4})
        counts = [sum(d.section_index == s for d in result) for s in range(3)]
        self.assertEqual(counts, [8, 4, 4])
        self.assertNotIn("s0-8", [d.prompt for d in result])

    def test_trim_keeps_biggest_section_at_quota(self):
        drafts = [make_draft(f"s0-{i}", section_index=0) for i in range(5)]
        drafts += [make_draft(f"s1-{i}", section_index=1) for i in range(3)]
        result = trim(drafts, 7, {0: 5, 1: 2})
        self.assertEqual([d.prompt for d in result if d.section_index == 0], [f"s0-{i}" for i in range(5)])
        self.assertNotIn("s1-2", [d.prompt for d in result])

    def test_trim_counts_section_without_quota_as_zero(self):
        drafts = [make_draft(f"s0-{i}", section_index=0) for i in range(3)]
        drafts.append(make_draft("extra", section_index=4))
        result = trim(drafts, 3, {0: 3})
        self.assertEqual([d.prompt for d in result], ["s0-0", "s0-1", "s0-2"])


class BalanceTests(SimpleTestCase):
    def drafts(self):
        return [make_draft(f"q{i}", correct_index=0) for i in range(8)]

    def test_balance_spreads_positions(self):
        before = self.drafts()
        result = balance_positions(before, seed=7)
        counts = sorted(d.correct_index for d in result)
        self.assertEqual(counts, [0, 0, 1, 1, 2, 2, 3, 3])
        for old, new in zip(before, result):
            self.assertEqual(new.choices[new.correct_index], old.choices[old.correct_index])
            self.assertIsNone(new.distractor_types[new.correct_index])
        self.assertEqual([d.correct_index for d in before], [0] * 8)
        self.assertEqual(before[0].choices, ["a1", "b2", "c3", "d4"])
        again = balance_positions(self.drafts(), seed=7)
        self.assertEqual([d.correct_index for d in again], [d.correct_index for d in result])

    def test_balance_keeps_choice_set(self):
        for old, new in zip(self.drafts(), balance_positions(self.drafts(), seed=3)):
            self.assertEqual(sorted(new.choices), sorted(old.choices))


class OrderTests(SimpleTestCase):
    def test_order_by_concept_then_difficulty(self):
        concepts = [Concept("c1", "One", 0, 0, {}), Concept("c2", "Two", 0, 1, {})]
        drafts = [
            make_draft("c2e", difficulty="easy", concept_id="c2"),
            make_draft("c1h", difficulty="hard", concept_id="c1"),
            make_draft("c1e", difficulty="easy", concept_id="c1"),
        ]
        self.assertEqual([d.prompt for d in order_drafts(drafts, concepts)], ["c1e", "c1h", "c2e"])

    def test_unknown_concept_sorts_last_and_stays_stable(self):
        concepts = [Concept("c1", "One", 0, 0, {})]
        drafts = [
            make_draft("x1", concept_id="zz"),
            make_draft("k", concept_id="c1"),
            make_draft("x2", concept_id="zz"),
        ]
        self.assertEqual([d.prompt for d in order_drafts(drafts, concepts)], ["k", "x1", "x2"])


class MixWarningTests(SimpleTestCase):
    def test_mix_warnings(self):
        long_correct = ["long long long", "b", "c", "d"]
        drafts = [make_draft(f"q{i}", choices=list(long_correct), difficulty="easy") for i in range(3)]
        drafts.append(make_draft("q3", choices=["a", "bbbb", "c", "d"], difficulty="medium"))
        warnings = mix_warnings(drafts)
        self.assertIn("longest_correct", warnings)
        self.assertIn("missing_hard", warnings)
        self.assertNotIn("missing_easy", warnings)

    def test_mix_warnings_empty(self):
        self.assertEqual(mix_warnings([]), [])


class DifficultySplitTests(SimpleTestCase):
    def test_exact_splits(self):
        expected = {
            1: {"easy": 0, "medium": 1, "hard": 0},
            2: {"easy": 1, "medium": 1, "hard": 0},
            3: {"easy": 1, "medium": 1, "hard": 1},
            5: {"easy": 1, "medium": 3, "hard": 1},
            6: {"easy": 2, "medium": 3, "hard": 1},
            7: {"easy": 2, "medium": 4, "hard": 1},
            10: {"easy": 3, "medium": 5, "hard": 2},
        }
        for count, split in expected.items():
            with self.subTest(count=count):
                self.assertEqual(difficulty_split(count), split)

    def test_split_sums_to_count_with_each_level_from_three(self):
        for count in range(0, 41):
            with self.subTest(count=count):
                split = difficulty_split(count)
                self.assertEqual(list(split), ["easy", "medium", "hard"])
                self.assertEqual(sum(split.values()), count)
                if count >= 3:
                    self.assertTrue(all(split.values()))


class UntouchedTests(SimpleTestCase):
    def values(self):
        return ("Why?", ["a", "b", "c", "d"], 1, "easy")

    def test_untouched_true_when_same(self):
        generation = {"original": original_of(*self.values())}
        self.assertTrue(is_untouched(*self.values(), generation))

    def test_untouched_false_when_any_field_edited(self):
        generation = {"original": original_of(*self.values())}
        prompt, choices, correct, difficulty = self.values()
        self.assertFalse(is_untouched("Why not?", choices, correct, difficulty, generation))
        self.assertFalse(is_untouched(prompt, ["a", "b", "c", "x"], correct, difficulty, generation))
        self.assertFalse(is_untouched(prompt, choices, 2, difficulty, generation))
        self.assertFalse(is_untouched(prompt, choices, correct, "hard", generation))

    def test_untouched_false_without_generation(self):
        self.assertFalse(is_untouched(*self.values(), None))
        self.assertFalse(is_untouched(*self.values(), {}))
