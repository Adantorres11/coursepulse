"""The transcription job: recording in, saved transcript out, then hand-off.

No database transaction stays open while ffmpeg or OpenAI runs.
"""

import logging
import tempfile
from collections import Counter
from pathlib import Path

import kombu.exceptions
import redis
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import media
from .job_errors import (
    FILE_MISSING,
    HANDOFF_FAILED,
    TOO_EXPENSIVE,
    TOO_LONG,
    TOO_SHORT,
    UNEXPECTED,
    PermanentError,
)
from .jobs import claim_transcription, fail, heartbeat, lecture_lock, refresh_db_connection
from .models import Lecture, TranscriptChunk
from .transcript_text import (
    check_transcript,
    collapse_repeats,
    join_chunk_texts,
    merge_segments,
    whisper_prompt,
)
from .whisper_client import MODEL, transcribe_chunk

CHUNK_SECONDS = 600
SAFE_BYTES = 24 * 1024 * 1024
PRICE_PER_MINUTE = 0.006
MIN_SECONDS = 10
READY_MESSAGE = "Transcript ready. Starting question generation."


def hand_off(lecture_id: int) -> None:
    """Queue question generation. The transcript stays saved if queueing fails."""
    from .tasks import generate_questions  # tasks.py imports this module

    try:
        generate_questions.delay(lecture_id)
    except (kombu.exceptions.OperationalError, redis.exceptions.RedisError):
        logging.getLogger(__name__).exception(
            "lecture=%s hand-off to question generation failed", lecture_id
        )
        fail(lecture_id, None, HANDOFF_FAILED)


def _check_length(duration: float | None) -> None:
    if not duration:
        return
    if duration > settings.TRANSCRIPTION_MAX_SECONDS:
        raise PermanentError(TOO_LONG.format(hours=settings.TRANSCRIPTION_MAX_SECONDS / 3600))
    if duration < MIN_SECONDS:
        raise PermanentError(TOO_SHORT)


def _overlap(span: tuple[float, float], start: float, end: float) -> float:
    return max(0.0, min(span[1], end) - max(span[0], start))


def _matches(row: TranscriptChunk, chunk: media.Chunk, source: str) -> bool:
    return (
        row.source_name == source
        and row.index == chunk.index
        and round(row.start_seconds, 2) == round(chunk.start, 2)
        and round(row.end_seconds, 2) == round(chunk.end, 2)
    )


def _reuse_transcript(lecture_id: int, token: str) -> bool:
    with transaction.atomic():
        updated = Lecture.objects.filter(pk=lecture_id, job_token=token).update(
            job_token="",
            progress_message=READY_MESSAGE,
            last_progress_at=timezone.now(),
            error_message="",
        )
        if updated == 0:
            return False
        transaction.on_commit(lambda: hand_off(lecture_id))
    return True


def run_transcription(
    lecture_id: int, token: str, attempt: int, log: logging.LoggerAdapter
) -> bool:
    """Transcribe one lecture. Return True when the hand-off was scheduled."""
    if not claim_transcription(lecture_id, token):
        log.info("already owned by another job, exiting")
        return False
    with lecture_lock(lecture_id, token) as got:
        if not got:
            log.info("lock held by another job, exiting")
            return False

        lecture = Lecture.objects.select_related("classroom").get(pk=lecture_id)
        if not lecture.recording:
            raise PermanentError(FILE_MISSING)
        source = lecture.recording.name

        if lecture.transcript and lecture.transcript_source == source:
            log.info("reusing the saved transcript")
            return _reuse_transcript(lecture_id, token)

        path = Path(lecture.recording.path)
        info = media.probe(path)
        _check_length(info.duration)

        heartbeat(lecture_id, token, "Preparing audio")
        silences, duration = media.find_silences(path, info.audio_index)
        _check_length(duration)
        start, end = media.speech_bounds(duration, silences)
        speech_seconds = (end - start) - sum(_overlap(s, start, end) for s in silences)

        minutes = (end - start) / 60
        estimated = minutes * PRICE_PER_MINUTE
        if estimated > settings.TRANSCRIPTION_MAX_COST_USD:
            log.warning(
                "over cost limit minutes=%.1f est_usd=%.3f limit_usd=%.2f",
                minutes, estimated, settings.TRANSCRIPTION_MAX_COST_USD,
            )
            raise PermanentError(TOO_EXPENSIVE)
        log.info("minutes=%.1f est_usd=%.3f", minutes, estimated)

        with tempfile.TemporaryDirectory(prefix=f"lecture-{lecture_id}-") as tmp:
            audio = Path(tmp) / "audio.mp3"
            media.normalize_audio(path, info.audio_index, start, end, audio)
            shifted = [
                (max(s, start) - start, min(e, end) - start)
                for s, e in silences
                if _overlap((s, e), start, end) > 0
            ]

            length = end - start
            if length <= CHUNK_SECONDS:
                plan = [media.Chunk(0, 0.0, length)]
            else:
                plan = media.plan_chunks(length, shifted, chunk_seconds=CHUNK_SECONDS)

            rows = list(lecture.transcript_chunks.all())
            by_index = {chunk.index: chunk for chunk in plan}
            if any(
                row.index not in by_index or not _matches(row, by_index[row.index], source)
                for row in rows
            ):
                log.info("discarding %d saved parts that do not match this plan", len(rows))
                lecture.transcript_chunks.all().delete()
                rows = []
            saved = {row.index: row for row in rows}

            for chunk in plan:
                if chunk.index in saved:
                    continue
                heartbeat(lecture_id, token, f"Transcribing part {chunk.index + 1} of {len(plan)}")
                if len(plan) == 1:
                    part = audio
                else:
                    part = Path(tmp) / f"part-{chunk.index}.mp3"
                    media.cut_chunk(audio, chunk, part)
                size = part.stat().st_size
                if size > SAFE_BYTES:
                    log.error("part %d too large bytes=%d", chunk.index, size)
                    raise PermanentError(UNEXPECTED)
                previous = saved.get(chunk.index - 1)
                prompt = whisper_prompt(
                    lecture.classroom.name, lecture.title, previous.text if previous else ""
                )
                result = transcribe_chunk(part, prompt)
                refresh_db_connection()
                saved[chunk.index] = TranscriptChunk.objects.create(
                    lecture_id=lecture_id,
                    index=chunk.index,
                    start_seconds=chunk.start,
                    end_seconds=chunk.end,
                    source_name=source,
                    text=result.text,
                    raw=result.raw,
                )

        rows = [saved[chunk.index] for chunk in plan]
        text = rows[0].text
        for row in rows[1:]:
            text = join_chunk_texts(text, row.text)
        clean, removed = collapse_repeats(text)
        check_transcript(clean, speech_seconds, removed)
        segments = merge_segments(
            [(row.start_seconds + start, row.raw.get("segments") or []) for row in rows]
        )
        languages = Counter(row.raw.get("language", "") for row in rows)
        language = languages.most_common(1)[0][0]

        refresh_db_connection()
        with transaction.atomic():
            lecture = (
                Lecture.objects.select_for_update()
                .filter(pk=lecture_id, job_token=token)
                .first()
            )
            if lecture is None:
                return False
            if lecture.recording.name != source:
                log.info("recording changed during transcription, discarding")
                return False
            lecture.transcript = clean
            lecture.raw_transcript = {
                "model": MODEL,
                "chunks": [
                    {
                        "index": row.index,
                        "start": row.start_seconds + start,
                        "end": row.end_seconds + start,
                        "language": row.raw.get("language", ""),
                        "text": row.text,
                        "raw": row.raw,
                    }
                    for row in rows
                ],
                "segments": segments,
            }
            lecture.transcript_language = language
            lecture.transcript_source = source
            lecture.audio_seconds = duration
            lecture.progress_message = READY_MESSAGE
            lecture.last_progress_at = timezone.now()
            lecture.job_token = ""
            lecture.error_message = ""
            lecture.save()
            lecture.transcript_chunks.all().delete()
            transaction.on_commit(lambda: hand_off(lecture_id))

    log.info(
        "transcript saved words=%d language=%s chunks=%d",
        len(clean.split()), language, len(rows),
    )
    return True
