"""The question generation job: saved transcript in, draft questions out.

No database transaction stays open while OpenAI runs.
"""

import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .job_errors import (
    BAD_OUTPUT,
    INTERRUPTED,
    NO_CONCEPTS,
    NOTICE_KEPT,
    NOTICE_SHORT,
    QUESTIONS_BUSY,
    QUESTIONS_TOO_EXPENSIVE,
    QUIZ_LOCKED,
    TIMEOUT,
    TOO_FEW_QUESTIONS,
    UNEXPECTED,
    PermanentError,
    TransientError,
)
from .jobs import (
    LostOwnership,
    claim_questions,
    fail,
    heartbeat,
    lecture_lock,
    refresh_db_connection,
)
from .models import Attempt, Lecture, Question
from .question_client import ask, cost_of, estimate_cost
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

STAGE1_EFFORT = "low"
STAGE2_EFFORT = "medium"
STAGE1_MAX_OUTPUT = 6000
STAGE2_MAX_OUTPUT = 12000
GOTCHA_MAX_OUTPUT = 12000
DIFFICULTY_TARGET = "about 30% easy, 50% medium, 20% hard, at least one of each"


@dataclass
class _Run:
    """Counts for one run, for the summary log line."""

    lecture_id: int
    token: str
    log: logging.LoggerAdapter
    started: float = field(default_factory=time.monotonic)
    sections: int = 0
    calls: int = 0
    reasks: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    kept: int = 0
    gotchas: int = 0
    drops: Counter = field(default_factory=Counter)

    def summary(self, generated: int) -> str:
        drops = ",".join(f"{reason}:{count}" for reason, count in sorted(self.drops.items()))
        return (
            f"questions done model={settings.QUESTION_MODEL} "
            f"effort={STAGE1_EFFORT}/{STAGE2_EFFORT} sections={self.sections} "
            f"calls={self.calls} reasks={self.reasks} input_tokens={self.input_tokens} "
            f"cached_tokens={self.cached_tokens} output_tokens={self.output_tokens} "
            f"cost_usd={self.cost:.4f} seconds={time.monotonic() - self.started:.1f} "
            f"kept={self.kept} generated={generated} gotchas={self.gotchas} "
            f"drops={drops or 'none'}"
        )


def run_question_generation(
    lecture_id: int, token: str, attempt: int, log: logging.LoggerAdapter
) -> bool:
    """Generate draft questions for one lecture. Return True when it was saved `ready`.

    Return False after any permanent failure (saved as `failed`), lost ownership,
    a deleted lecture, a timeout, or an unexpected error. Raise only TransientError,
    so the task can retry.
    """
    if not claim_questions(lecture_id, token, allow_own=attempt > 0):
        if attempt == 0 and Lecture.objects.filter(
            pk=lecture_id, status="processing", job_token=token
        ).exists():
            # The broker sent this first message again after a worker crash. Running it
            # would pay for every call again, so fail it and let the professor retry.
            log.warning("redelivered message; failing without a paid call")
            fail(lecture_id, token, INTERRUPTED)
            return False
        log.info("already owned by another job, exiting")
        return False
    with lecture_lock(lecture_id, token, stage="questions") as got:
        if not got:
            log.info("question lock held by another job")
            raise TransientError(QUESTIONS_BUSY)
        try:
            return _generate(_Run(lecture_id, token, log))
        except PermanentError as exc:
            log.warning("failed %s: %s", type(exc).__name__, exc.message)
            fail(lecture_id, token, exc.message)
        except LostOwnership:
            log.info("no longer owns this lecture, exiting")
        except Lecture.DoesNotExist:
            log.info("lecture was deleted, exiting")
        except SoftTimeLimitExceeded:
            log.warning("soft time limit reached")
            fail(lecture_id, token, TIMEOUT)
        except TransientError:
            raise
        except Exception:
            log.exception("unexpected error")
            fail(lecture_id, token, UNEXPECTED)
    return False


def _check_guard(lecture: Lecture) -> None:
    if lecture.published_at is not None or Attempt.objects.filter(lecture_id=lecture.id).exists():
        raise PermanentError(QUIZ_LOCKED)


def _is_kept(question: Question) -> bool:
    """Hand-written questions, and generated ones the professor changed."""
    if question.generation is None:
        return True
    return not is_untouched(
        question.prompt,
        question.choices,
        question.correct_index,
        question.difficulty,
        question.generation,
    )


def _as_draft(question: Question) -> Draft:
    generation = question.generation or {}
    return Draft(
        prompt=question.prompt,
        choices=list(question.choices),
        correct_index=question.correct_index,
        difficulty=question.difficulty,
        reason="",
        concept_id=generation.get("concept_id") or "",
        pattern=generation.get("pattern") or "",
        gotcha=False,
        distractor_types=[None] * 4,
        section_index=-1,
    )


def _call(run: _Run, *, schema_name: str, schema: dict, instructions: str,
          user_input: str, effort: str, max_output_tokens: int) -> dict:
    """Make one model call, with one re-ask on an unusable reply. Every model call goes here.

    Before each request, stop when the spend so far plus its estimate is over the cap.
    """
    model = settings.QUESTION_MODEL
    for tries in (1, 2):
        estimate = estimate_cost(len(instructions) + len(user_input), max_output_tokens, model)
        if run.cost + estimate > settings.QUESTION_MAX_COST_USD:
            run.log.warning(
                "over cost limit spent_usd=%.4f est_usd=%.4f limit_usd=%.2f",
                run.cost, estimate, settings.QUESTION_MAX_COST_USD,
            )
            raise PermanentError(QUESTIONS_TOO_EXPENSIVE)
        if tries == 2:
            run.reasks += 1
        reply = ask(
            schema_name=schema_name,
            schema=schema,
            instructions=instructions,
            user_input=user_input,
            effort=effort,
            max_output_tokens=max_output_tokens,
            cache_key=f"lecture-{run.lecture_id}",
        )
        run.calls += 1
        run.input_tokens += reply.usage.input_tokens
        run.cached_tokens += reply.usage.cached_tokens
        run.output_tokens += reply.usage.output_tokens
        run.cost += cost_of(reply.usage, model)
        items = (reply.data or {}).get(schema_name)
        if not reply.problem and isinstance(items, list):
            return reply.data
        run.log.warning(
            "unusable reply schema=%s problem=%s try=%d",
            schema_name, reply.problem or "shape", tries,
        )
    raise PermanentError(BAD_OUTPUT)


def _concept_list(concepts: list[Concept]) -> str:
    rows = [
        {"id": c.id, "name": c.name, **{k: v for k, v in c.data.items() if k != "name"}}
        for c in concepts
    ]
    return json.dumps(rows, indent=1, ensure_ascii=False)


def _question_lines(drafts: list[Draft]) -> list[str]:
    return [
        f"- [{d.concept_id or 'none'}] {d.prompt} Answer: {d.choices[d.correct_index]}"
        for d in drafts
    ]


def _question_input(
    concept_text: str,
    kept: list[Draft],
    marked: list[str],
    section: Section,
    count: int,
    accepted_here: list[Draft],
) -> str:
    # The concept list and kept questions are the same in every call, so they go first
    # for prompt caching.
    parts = ["FULL CONCEPT LIST", concept_text]
    if kept:
        parts += ["", "QUESTIONS THAT ALREADY EXIST (do not repeat them)", *_question_lines(kept)]
    parts += ["", f"Concepts from this section: {', '.join(marked)}"]
    if accepted_here:
        parts += [
            "Questions already written for this section (do not repeat them)",
            *_question_lines(accepted_here),
        ]
    parts += [
        f"Questions to write: {count}",
        f"Difficulty target: {DIFFICULTY_TARGET}",
        "",
        "SECTION TRANSCRIPT",
        section.text,
    ]
    return "\n".join(parts)


def _gotcha_input(concept_text: str, accepted: list[Draft], count: int, transcript: str) -> str:
    return "\n".join([
        "FULL CONCEPT LIST",
        concept_text,
        "",
        "ACCEPTED QUESTIONS",
        *_question_lines(accepted),
        "",
        f"Questions to write: {count}",
        "",
        "TRANSCRIPT",
        transcript,
    ])


def _generate(run: _Run) -> bool:
    lecture_id, token, log = run.lecture_id, run.token, run.log
    lecture = Lecture.objects.get(pk=lecture_id)
    _check_guard(lecture)

    kept = [q for q in lecture.questions.all() if _is_kept(q)]
    run.kept = len(kept)
    target = target_count(len(lecture.transcript.split()))
    needed = target - len(kept)
    if needed <= 0:
        log.info("kept=%d target=%d, no new questions needed", len(kept), target)
        return _save(run, [], [], [], target)

    sections = split_sections(lecture.transcript, lecture.raw_transcript)
    run.sections = len(sections)

    names_by_section: list[tuple[int, list[dict]]] = []
    for i, section in enumerate(sections, start=1):
        heartbeat(lecture_id, token, f"Finding key concepts (part {i} of {len(sections)})")
        data = _call(
            run,
            schema_name="concepts",
            schema=CONCEPT_SCHEMA,
            instructions=CONCEPT_INSTRUCTIONS,
            user_input=section.text,
            effort=STAGE1_EFFORT,
            max_output_tokens=STAGE1_MAX_OUTPUT,
        )
        found = [
            c for c in data["concepts"] if isinstance(c, dict) and isinstance(c.get("name"), str)
        ]
        names_by_section.append((section.index, found))

    concepts = merge_concepts(names_by_section)
    if not concepts:
        raise PermanentError(NO_CONCEPTS)
    concept_ids = {c.id for c in concepts}
    marked = {
        index: concept_ids_for([c["name"] for c in found], concepts)
        for index, found in names_by_section
    }
    with_concepts = {index for index, ids in marked.items() if ids}
    quotas = section_quotas(needed, sections, with_concepts)
    log.info(
        "concepts=%d target=%d kept=%d needed=%d", len(concepts), target, len(kept), needed
    )

    kept_drafts = [_as_draft(q) for q in kept]
    accepted = QuestionSet(kept_drafts)
    concept_text = _concept_list(concepts)
    asked = [s for s in sections if quotas[s.index] > 0]

    def write_questions(section: Section, count: int, accepted_here: list[Draft]) -> None:
        data = _call(
            run,
            schema_name="questions",
            schema=QUESTION_SCHEMA,
            instructions=QUESTION_INSTRUCTIONS,
            user_input=_question_input(
                concept_text, kept_drafts, marked[section.index], section, count, accepted_here
            ),
            effort=STAGE2_EFFORT,
            max_output_tokens=STAGE2_MAX_OUTPUT,
        )
        for raw in data["questions"]:
            _accept(run, accepted, raw, concept_ids, section.index)

    for i, section in enumerate(asked, start=1):
        heartbeat(lecture_id, token, f"Writing questions (part {i} of {len(asked)})")
        write_questions(section, quotas[section.index] + 1, [])

    # Replacement round: one more call, and only one, per section short of its quota.
    for section in asked:
        here = [d for d in accepted.new if d.section_index == section.index]
        gap = quotas[section.index] - len(here)
        if gap > 0:
            heartbeat(lecture_id, token, "Writing more questions")
            write_questions(section, gap, here)

    # Gotcha pass: one call when kept plus new is still under the minimum.
    total = len(kept_drafts) + len(accepted.new)
    if total < settings.QUESTION_MIN_COUNT:
        heartbeat(lecture_id, token, "Writing more questions")
        data = _call(
            run,
            schema_name="questions",
            schema=QUESTION_SCHEMA,
            instructions=GOTCHA_INSTRUCTIONS,
            user_input=_gotcha_input(
                concept_text, kept_drafts + accepted.new, target - total, lecture.transcript
            ),
            effort=STAGE2_EFFORT,
            max_output_tokens=GOTCHA_MAX_OUTPUT,
        )
        first_section = {c.id: c.section_index for c in concepts}
        for raw in data["questions"]:
            if isinstance(raw, dict):
                raw = {**raw, "gotcha": True}  # every draft from this pass is a gotcha
            concept_id = raw.get("concept_id") if isinstance(raw, dict) else None
            section_index = first_section.get(concept_id, -1) if isinstance(concept_id, str) else -1
            _accept(run, accepted, raw, concept_ids, section_index)

    heartbeat(lecture_id, token, "Checking questions")
    drafts = trim(accepted.new, needed, quotas)
    drafts = balance_positions(drafts, seed=lecture_id)
    drafts = order_drafts(drafts, concepts)
    for warning in mix_warnings(drafts):
        log.warning("question mix warning=%s", warning)

    return _save(run, drafts, concepts, sections, target)


def _accept(run: _Run, accepted: QuestionSet, raw, concept_ids: set[str], section_index: int):
    draft, reason = check_draft(raw, concept_ids, section_index)
    if draft is not None:
        reason = accepted.add(draft)
    if reason:
        concept = raw.get("concept_id") if isinstance(raw, dict) else None
        concept = concept[:20] if isinstance(concept, str) else "?"
        run.log.info("drop reason=%s section=%d concept=%s", reason, section_index, concept)
        run.drops[reason] += 1
        return
    flags = soft_flags(draft)
    if flags:
        run.log.debug(
            "soft phrases section=%d concept=%s flags=%s",
            section_index, draft.concept_id, ",".join(flags),
        )


def _generation(draft: Draft, concepts: dict[str, Concept], sections: dict[int, Section]) -> dict:
    section = sections[draft.section_index]
    return {
        "concept": concepts[draft.concept_id].name,
        "concept_id": draft.concept_id,
        "pattern": draft.pattern,
        "reason": draft.reason,
        "gotcha": draft.gotcha,
        "distractor_types": list(draft.distractor_types),
        "section": {
            "index": section.index,
            "start_seconds": section.start,
            "end_seconds": section.end,
        },
        "model": settings.QUESTION_MODEL,
        "original": original_of(
            draft.prompt, draft.choices, draft.correct_index, draft.difficulty
        ),
    }


def _notice(log: logging.LoggerAdapter, kept: int, new: int, target: int) -> str:
    """Fail under the floor. Otherwise return the notice for a short or fully kept set."""
    total = kept + new
    if total < settings.QUESTION_FLOOR_COUNT:
        log.warning("too few questions total=%d floor=%d", total, settings.QUESTION_FLOOR_COUNT)
        raise PermanentError(TOO_FEW_QUESTIONS.format(count=total))
    if new == 0 and kept >= target:
        return NOTICE_KEPT.format(count=kept)
    if total < settings.QUESTION_MIN_COUNT:
        log.warning("short question set total=%d target=%d", total, target)
        return NOTICE_SHORT.format(count=total, target=target)
    return ""


def _save(
    run: _Run,
    drafts: list[Draft],
    concepts: list[Concept],
    sections: list[Section],
    target: int,
) -> bool:
    """Save in one transaction. The floor and the notice use the kept count at save time."""
    lecture_id, token, log = run.lecture_id, run.token, run.log
    heartbeat(lecture_id, token, "Saving questions")
    by_concept = {c.id: c for c in concepts}
    by_section = {s.index: s for s in sections}
    refresh_db_connection()
    with transaction.atomic():
        lecture = (
            Lecture.objects.select_for_update()
            .filter(pk=lecture_id, job_token=token)
            .first()
        )
        if lecture is None:
            log.info("no longer owns this lecture, exiting")
            return False
        _check_guard(lecture)
        # The professor may have edited questions during the run.
        questions = list(lecture.questions.select_for_update())
        kept = [q for q in questions if _is_kept(q)]
        notice = _notice(log, len(kept), len(drafts), target)
        Question.objects.filter(pk__in=[q.pk for q in questions if not _is_kept(q)]).delete()
        for position, question in enumerate(kept):
            if question.position != position:
                Question.objects.filter(pk=question.pk).update(position=position)
        for offset, draft in enumerate(drafts):
            Question.objects.create(
                lecture=lecture,
                prompt=draft.prompt,
                choices=draft.choices,
                correct_index=draft.correct_index,
                difficulty=draft.difficulty,
                position=len(kept) + offset,
                generation=_generation(draft, by_concept, by_section),
            )
        run.kept = len(kept)
        run.gotchas = sum(draft.gotcha for draft in drafts)
        lecture.status = "ready"
        lecture.job_token = ""
        lecture.progress_message = ""
        lecture.error_message = ""
        lecture.notice = notice
        lecture.last_progress_at = timezone.now()
        lecture.save(
            update_fields=[
                "status", "job_token", "progress_message", "error_message", "notice",
                "last_progress_at",
            ]
        )
    log.info(run.summary(generated=len(drafts)))
    return True
