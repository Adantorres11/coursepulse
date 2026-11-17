from django.test import SimpleTestCase

from .job_errors import INCOMPLETE, NO_SPEECH, PermanentError
from .transcript_text import (
    check_transcript,
    collapse_repeats,
    join_chunk_texts,
    merge_segments,
    whisper_prompt,
)


def words(n):
    return " ".join(f"word{i}" for i in range(n))


class JoinChunkTextsTests(SimpleTestCase):
    def test_join_removes_duplicated_overlap_words(self):
        self.assertEqual(
            join_chunk_texts(
                "we covered the binary search tree today",
                "Binary search tree today, and then heaps.",
            ),
            "we covered the binary search tree today and then heaps.",
        )

    def test_join_without_overlap_keeps_both(self):
        self.assertEqual(
            join_chunk_texts("first part.", "second part."),
            "first part. second part.",
        )


class MergeSegmentsTests(SimpleTestCase):
    def test_merge_segments_shifts_timestamps_and_drops_overlap(self):
        merged = merge_segments([
            (0.0, [{"start": 0, "end": 599, "text": "a"}]),
            (598.0, [
                {"start": 0, "end": 1.5, "text": "a"},
                {"start": 1.5, "end": 9, "text": "b"},
            ]),
        ])
        self.assertEqual([s["text"] for s in merged], ["a", "b"])
        self.assertEqual(merged[1]["start"], 599.5)
        self.assertEqual(merged[1]["end"], 607)

    def test_merge_segments_keeps_only_start_end_text(self):
        merged = merge_segments([
            (0.0, [{"start": 0, "end": 1, "text": "a", "id": 3, "avg_logprob": -0.1}]),
        ])
        self.assertEqual(merged, [{"start": 0.0, "end": 1.0, "text": "a"}])


class CollapseRepeatsTests(SimpleTestCase):
    def test_collapse_repeats_keeps_one_copy_of_long_runs(self):
        text = "Real lecture text here. " + "Thanks for watching. " * 6
        clean, removed = collapse_repeats(text)
        self.assertEqual(clean.count("Thanks for watching."), 1)
        self.assertEqual(removed, 15)

    def test_collapse_repeats_keeps_three_in_a_row(self):
        text = "Yes. Yes. Yes."
        clean, removed = collapse_repeats(text)
        self.assertEqual(clean, "Yes. Yes. Yes.")
        self.assertEqual(removed, 0)


class CheckTranscriptTests(SimpleTestCase):
    def test_check_transcript_too_few_words_is_no_speech(self):
        with self.assertRaises(PermanentError) as ctx:
            check_transcript("Thanks.", 600, 0)
        self.assertEqual(ctx.exception.message, NO_SPEECH)

    def test_check_transcript_mostly_repeats_is_no_speech(self):
        with self.assertRaises(PermanentError) as ctx:
            check_transcript(words(12), 600, 40)
        self.assertEqual(ctx.exception.message, NO_SPEECH)

    def test_check_transcript_low_wpm_is_incomplete(self):
        with self.assertRaises(PermanentError) as ctx:
            check_transcript(words(50), 600, 0)
        self.assertEqual(ctx.exception.message, INCOMPLETE)

    def test_check_transcript_short_clip_skips_wpm(self):
        check_transcript(words(15), 60, 0)

    def test_check_transcript_normal_lecture_passes(self):
        check_transcript(words(1500), 600, 0)


class WhisperPromptTests(SimpleTestCase):
    def test_whisper_prompt_has_class_title_and_tail(self):
        p = whisper_prompt("Any Class", "Week 3", " ".join(f"w{i}" for i in range(200)))
        self.assertTrue(p.startswith("Any Class. Week 3. w150"))
        self.assertTrue(p.endswith("w199"))
        self.assertLessEqual(len(p), 800)

    def test_whisper_prompt_cuts_from_the_start_over_800_chars(self):
        p = whisper_prompt("C", "T", " ".join(["x" * 20] * 50) + " last")
        self.assertEqual(len(p), 800)
        self.assertTrue(p.endswith("last"))
