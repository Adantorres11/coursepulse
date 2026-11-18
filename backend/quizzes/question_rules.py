"""Pure rules for question generation: counts, sections, and concepts. No database, no network."""

import difflib
import re
from dataclasses import dataclass

from django.conf import settings

SECTION_WORDS = 1300
CONCEPT_MATCH_RATIO = 0.85

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


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
