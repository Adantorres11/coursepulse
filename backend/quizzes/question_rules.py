"""Pure rules for question generation: counts, sections, and concepts. No database, no network."""

import difflib
import math
import random
import re
from dataclasses import dataclass, replace

from django.conf import settings

SECTION_WORDS = 1300
CONCEPT_MATCH_RATIO = 0.85
NEAR_DUPLICATE_RATIO = 0.8
MAX_PROMPT_CHARS = 500
MAX_CHOICE_CHARS = 200
DIFFICULTIES = ("easy", "medium", "hard")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

_HARD_DROP = re.compile(
    r"\b(professor|instructor|lecturer|speaker)s?\b"
    r"|\bwhat did\b.*\b(say|said|mention|mentioned)\b"
    r"|\b(homework|due date|midterm|final exam|attendance|syllabus|office hours|extra credit|grading)\b",
    re.IGNORECASE | re.DOTALL,
)
_SOFT_PHRASES = re.compile(
    r"\b(said|mentioned|the lecture|this lecture|in class|this class)\b", re.IGNORECASE
)
_NONE_ABOVE = {"none of the above", "all of the above", "none of these", "all of these"}
_CHOICE_REFERENCE = (
    re.compile(r"\b(both|all|none|neither) of the above\b", re.IGNORECASE),
    re.compile(r"\b(?i:options?|choices?|answers?)\s+(?:[A-D]|[1-4])\b"),
    re.compile(r"\b(?i:both|either|neither)\s+[A-D]\s+(?i:and|or|nor)\s+[A-D]\b"),
    re.compile(r"^\s*[A-D]\s*(?:(?i:and|or)|&|,)\s*[A-D]\s*$"),
)


@dataclass(frozen=True)
class Section:
    index: int
    start: float | None
    end: float | None
    text: str

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class Concept:
    id: str  # "c1", "c2", ... in lecture order
    name: str
    section_index: int  # first section it appeared in
    order: int  # global order of first appearance
    data: dict  # the stage 1 fields


def target_count(words: int) -> int:
    wanted = round(words / settings.QUESTION_WORDS_PER_QUESTION)
    return max(settings.QUESTION_MIN_COUNT, min(settings.QUESTION_MAX_COUNT, wanted))


def _sections_from_chunks(raw: dict | None) -> list[Section]:
    chunks = (raw or {}).get("chunks") or []
    return [
        Section(chunk["index"], chunk.get("start"), chunk.get("end"), chunk["text"].strip())
        for chunk in chunks
        if (chunk.get("text") or "").strip()
    ]


def _sections_from_text(transcript: str) -> list[Section]:
    sentences = _SENTENCE_SPLIT.split(transcript.strip()) if transcript.strip() else []
    pieces: list[list[str]] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        current.append(sentence)
        current_words += len(sentence.split())
        if current_words >= SECTION_WORDS:
            pieces.append(current)
            current, current_words = [], 0
    if current:
        # A short tail joins the piece before it, so no section is tiny.
        if pieces and current_words < SECTION_WORDS / 2:
            pieces[-1].extend(current)
        else:
            pieces.append(current)
    return [Section(i, None, None, " ".join(piece)) for i, piece in enumerate(pieces)]


def split_sections(transcript: str, raw: dict | None) -> list[Section]:
    """Use the saved Whisper chunks, or split the plain text at sentence ends."""
    return _sections_from_chunks(raw) or _sections_from_text(transcript)


def _concept_key(name: str) -> str:
    key = name.strip().lower()
    return key[:-1] if key.endswith("s") else key


def merge_concepts(per_section: list[tuple[int, list[dict]]]) -> list[Concept]:
    """Give concepts global ids in lecture order and merge repeats across sections."""
    merged: list[Concept] = []
    keys: list[str] = []
    for section_index, concepts in sorted(per_section, key=lambda pair: pair[0]):
        for data in concepts:
            name = data["name"].strip()
            key = _concept_key(name)
            if not key:
                continue
            if any(
                difflib.SequenceMatcher(None, key, seen).ratio() >= CONCEPT_MATCH_RATIO
                for seen in keys
            ):
                continue
            order = len(merged)
            merged.append(Concept(f"c{order + 1}", name, section_index, order, data))
            keys.append(key)
    return merged


def concept_ids_for(names: list[str], concepts: list[Concept]) -> list[str]:
    """Map one section's concept names to merged ids, with the matching merge_concepts uses."""
    ids: list[str] = []
    for name in names:
        key = _concept_key(name)
        if not key:
            continue
        for concept in concepts:
            ratio = difflib.SequenceMatcher(None, key, _concept_key(concept.name)).ratio()
            if ratio >= CONCEPT_MATCH_RATIO:
                if concept.id not in ids:
                    ids.append(concept.id)
                break
    return ids

@dataclass
class Draft:
    prompt: str
    choices: list[str]
    correct_index: int
    difficulty: str
    reason: str
    concept_id: str
    pattern: str
    gotcha: bool
    distractor_types: list[str | None]
    section_index: int


def _normalize(text: str) -> str:
    return " ".join(text.lower().split()).rstrip(".,;:!? ")


def _has_shape(raw: dict) -> bool:
    if not isinstance(raw, dict):
        return False
    texts = ("prompt", "difficulty", "reason", "concept_id", "pattern")
    if not all(isinstance(raw.get(key), str) for key in texts):
        return False
    choices = raw.get("choices")
    types = raw.get("distractor_types")
    return (
        isinstance(choices, list)
        and len(choices) == 4
        and all(isinstance(choice, str) for choice in choices)
        and isinstance(raw.get("correct_index"), int)
        and not isinstance(raw["correct_index"], bool)
        and isinstance(raw.get("gotcha"), bool)
        and isinstance(types, list)
        and len(types) == 4
        and all(item is None or isinstance(item, str) for item in types)
    )


def _failure(raw: dict, concept_ids: set[str]) -> str:
    if not _has_shape(raw):
        return "shape"
    prompt, choices = raw["prompt"], raw["choices"]
    normalized = [_normalize(choice) for choice in choices]
    if not _normalize(prompt) or not all(normalized):
        return "blank_choice"
    if len(set(normalized)) < 4:
        return "duplicate_choices"
    if not 0 <= raw["correct_index"] <= 3:
        return "bad_index"
    if raw["difficulty"] not in DIFFICULTIES:
        return "bad_difficulty"
    if len(prompt) > MAX_PROMPT_CHARS or any(len(choice) > MAX_CHOICE_CHARS for choice in choices):
        return "too_long"
    if any(text in _NONE_ABOVE for text in normalized):
        return "all_none_above"
    if any(rule.search(choice) for rule in _CHOICE_REFERENCE for choice in choices):
        return "choice_reference"
    if raw["concept_id"] not in concept_ids:
        return "unknown_concept"
    if any(_HARD_DROP.search(text) for text in (prompt, *choices)):
        return "speaker_or_logistics"
    return ""


def check_draft(raw: dict, concept_ids: set[str], section_index: int) -> tuple[Draft | None, str]:
    """Return (draft, "") for a usable question, or (None, reason) for the first failed rule."""
    reason = _failure(raw, concept_ids)
    if reason:
        return None, reason
    return (
        Draft(
            prompt=raw["prompt"],
            choices=list(raw["choices"]),
            correct_index=raw["correct_index"],
            difficulty=raw["difficulty"],
            reason=raw["reason"],
            concept_id=raw["concept_id"],
            pattern=raw["pattern"],
            gotcha=raw["gotcha"],
            distractor_types=list(raw["distractor_types"]),
            section_index=section_index,
        ),
        "",
    )


def soft_flags(draft: Draft) -> list[str]:
    """Softer phrases the prompt forbids but code keeps. For the debug log only."""
    text = " ".join([draft.prompt, *draft.choices])
    return sorted({match.group(0).lower() for match in _SOFT_PHRASES.finditer(text)})


class QuestionSet:
    """Accepted questions plus kept ones, so new questions do not repeat or crowd a grid cell."""

    def __init__(self, kept: list[Draft]):
        self._all: list[Draft] = list(kept)
        self._cells: set[tuple[str, str, str]] = {
            self._cell(draft) for draft in kept if draft.concept_id and not draft.gotcha
        }
        self._new: list[Draft] = []

    @staticmethod
    def _cell(draft: Draft) -> tuple[str, str, str]:
        return (draft.concept_id, draft.pattern, draft.difficulty)

    @staticmethod
    def _answer(draft: Draft) -> str:
        return _normalize(draft.choices[draft.correct_index])

    def _is_near_duplicate(self, draft: Draft) -> bool:
        answer, prompt = self._answer(draft), _normalize(draft.prompt)
        for other in self._all:
            if draft.concept_id and other.concept_id and draft.concept_id != other.concept_id:
                continue
            if self._answer(other) != answer:
                continue
            ratio = difflib.SequenceMatcher(None, prompt, _normalize(other.prompt)).ratio()
            if ratio >= NEAR_DUPLICATE_RATIO:
                return True
        return False

    def add(self, draft: Draft) -> str:
        if self._is_near_duplicate(draft):
            return "near_duplicate"
        occupies = bool(draft.concept_id) and not draft.gotcha
        if occupies and self._cell(draft) in self._cells:
            return "grid_full"
        if occupies:
            self._cells.add(self._cell(draft))
        self._all.append(draft)
        self._new.append(draft)
        return ""

    @property
    def new(self) -> list[Draft]:
        return list(self._new)


def section_quotas(needed: int, sections: list[Section], with_concepts: set[int]) -> dict[int, int]:
    """Split needed questions across sections by word share, using the largest remainder method."""
    quotas = {section.index: 0 for section in sections}
    eligible = [s for s in sections if s.index in with_concepts]
    total_words = sum(s.words for s in eligible)
    if not eligible or needed <= 0:
        return quotas
    weights = {s.index: s.words if total_words else 1 for s in eligible}
    total = sum(weights.values())
    remainders = {}
    for index, weight in weights.items():
        quotas[index], remainders[index] = divmod(needed * weight, total)
    left = needed - sum(quotas.values())
    for index in sorted(remainders, key=lambda i: (-remainders[i], i))[:left]:
        quotas[index] += 1
    return quotas


def trim(drafts: list[Draft], needed: int) -> list[Draft]:
    """Drop extras from the section with the most drafts (higher index on ties), last draft first."""
    result = list(drafts)
    while len(result) > max(needed, 0):
        counts: dict[int, int] = {}
        for draft in result:
            counts[draft.section_index] = counts.get(draft.section_index, 0) + 1
        section = max(counts, key=lambda index: (counts[index], index))
        last = max(i for i, draft in enumerate(result) if draft.section_index == section)
        del result[last]
    return result


def balance_positions(drafts: list[Draft], seed: int) -> list[Draft]:
    """Spread correct answers over positions 0 to 3 by swapping choices. Returns new drafts."""
    targets = ([0, 1, 2, 3] * math.ceil(len(drafts) / 4))[: len(drafts)]
    random.Random(seed).shuffle(targets)
    result = []
    for draft, target in zip(drafts, targets):
        choices = list(draft.choices)
        types = list(draft.distractor_types)
        current = draft.correct_index
        choices[current], choices[target] = choices[target], choices[current]
        types[current], types[target] = types[target], types[current]
        result.append(replace(draft, choices=choices, distractor_types=types, correct_index=target))
    return result


def order_drafts(drafts: list[Draft], concepts: list[Concept]) -> list[Draft]:
    """Sort by the concept's first appearance, then easy, medium, hard. Unknown concepts go last."""
    order = {concept.id: concept.order for concept in concepts}
    return sorted(
        drafts,
        key=lambda d: (order.get(d.concept_id, len(order)), DIFFICULTIES.index(d.difficulty)),
    )


def mix_warnings(drafts: list[Draft]) -> list[str]:
    if not drafts:
        return []
    warnings = []
    longest = sum(
        1
        for d in drafts
        if all(
            len(d.choices[d.correct_index]) > len(choice)
            for i, choice in enumerate(d.choices)
            if i != d.correct_index
        )
    )
    if longest / len(drafts) > 0.4:
        warnings.append("longest_correct")
    present = {d.difficulty for d in drafts}
    warnings.extend(f"missing_{level}" for level in DIFFICULTIES if level not in present)
    return warnings


def original_of(prompt: str, choices: list[str], correct_index: int, difficulty: str) -> dict:
    return {
        "prompt": prompt,
        "choices": list(choices),
        "correct_index": correct_index,
        "difficulty": difficulty,
    }


def is_untouched(
    prompt: str, choices: list, correct_index: int, difficulty: str, generation: dict | None
) -> bool:
    original = (generation or {}).get("original")
    if not original:
        return False
    return original == original_of(prompt, choices, correct_index, difficulty)
