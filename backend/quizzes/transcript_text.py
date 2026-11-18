"""Pure text rules for joining and cleaning Whisper transcripts."""

import re

from .job_errors import INCOMPLETE, NO_SPEECH, PermanentError

MIN_WORDS = 10
MIN_WPM_SECONDS = 120
MIN_WPM = 30
PROMPT_TAIL_WORDS = 50
PROMPT_MAX_CHARS = 800

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NOT_WORD_CHARS = re.compile(r"[^\w\s]")


def _normalize(text: str) -> str:
    return _NOT_WORD_CHARS.sub("", text.lower()).strip()


def join_chunk_texts(previous: str, following: str, max_overlap_words: int = 30) -> str:
    """Join two chunk texts and drop words repeated in the chunk overlap."""
    previous_words = previous.split()
    following_words = following.split()
    previous_norm = [_normalize(w) for w in previous_words]
    following_norm = [_normalize(w) for w in following_words]

    most = min(max_overlap_words, len(previous_words), len(following_words))
    for k in range(most, 1, -1):
        if previous_norm[-k:] == following_norm[:k]:
            following_words = following_words[k:]
            break
    return " ".join(previous_words + following_words)


def merge_segments(chunks: list[tuple[float, list[dict]]]) -> list[dict]:
    """Shift segment times by chunk start and drop segments in chunk overlaps."""
    merged: list[dict] = []
    for index, (chunk_start, segments) in enumerate(chunks):
        for segment in segments:
            start = segment["start"] + chunk_start
            end = segment["end"] + chunk_start
            if index > 0 and merged and (start + end) / 2 < merged[-1]["end"]:
                continue
            merged.append({"start": start, "end": end, "text": segment["text"]})
    return merged


def collapse_repeats(text: str, max_run: int = 3) -> tuple[str, int]:
    """Shrink runs of more than `max_run` equal sentences to one copy."""
    sentences = _SENTENCE_SPLIT.split(text.strip()) if text.strip() else []
    kept: list[str] = []
    removed_words = 0
    i = 0
    while i < len(sentences):
        key = _normalize(sentences[i])
        j = i
        while j < len(sentences) and _normalize(sentences[j]) == key:
            j += 1
        run = sentences[i:j]
        if len(run) > max_run:
            kept.append(run[0])
            removed_words += sum(len(s.split()) for s in run[1:])
        else:
            kept.extend(run)
        i = j
    return " ".join(kept), removed_words


def check_transcript(text: str, speech_seconds: float, removed_words: int) -> None:
    """Raise PermanentError when the transcript is empty or looks incomplete."""
    word_count = len(text.split())
    if word_count < MIN_WORDS or removed_words > (removed_words + word_count) / 2:
        raise PermanentError(NO_SPEECH)
    if speech_seconds >= MIN_WPM_SECONDS and word_count / (speech_seconds / 60) < MIN_WPM:
        raise PermanentError(INCOMPLETE)


def whisper_prompt(class_name: str, title: str, previous_text: str) -> str:
    """Build the Whisper prompt: class, title, and the end of the earlier text."""
    tail = " ".join(previous_text.split()[-PROMPT_TAIL_WORDS:])
    prompt = f"{class_name}. {title}. {tail}".strip()
    return prompt[-PROMPT_MAX_CHARS:]
