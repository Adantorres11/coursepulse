"""One call to the OpenAI Whisper API, with errors mapped to job errors."""

from dataclasses import dataclass
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from .job_errors import (
    BAD_KEY,
    NO_CREDITS,
    NO_KEY,
    SERVICE_BUSY,
    UNEXPECTED,
    UNREADABLE,
    PermanentError,
    TransientError,
)

MODEL = "whisper-1"
TIMEOUT_SECONDS = 120.0
OUT_OF_CREDITS = {"insufficient_quota", "credit_balance_exhausted"}


@dataclass(frozen=True)
class WhisperResult:
    text: str
    language: str
    duration: float
    segments: list[dict]
    raw: dict


def _find_soft_limit(exc):
    """Return a SoftTimeLimitExceeded in the cause chain of exc, or None."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, SoftTimeLimitExceeded):
            return exc
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return None


def _is_out_of_credits(exc):
    values = [exc.code, exc.type]
    if isinstance(exc.body, dict):
        values += [exc.body.get("code"), exc.body.get("type")]
    return any(value in OUT_OF_CREDITS for value in values)


def _map_error(exc):
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return PermanentError(BAD_KEY)
    if isinstance(exc, RateLimitError):
        if _is_out_of_credits(exc):
            return PermanentError(NO_CREDITS)
        return TransientError(SERVICE_BUSY)
    if isinstance(exc, (APITimeoutError, APIConnectionError, InternalServerError)):
        return TransientError(SERVICE_BUSY)
    if isinstance(exc, BadRequestError):
        return PermanentError(UNREADABLE)
    if isinstance(exc, APIStatusError):
        return PermanentError(UNEXPECTED)
    return None


def transcribe_chunk(path: Path, prompt: str, client_factory=OpenAI) -> WhisperResult:
    if not settings.OPENAI_API_KEY:
        raise PermanentError(NO_KEY)
    client = client_factory(
        api_key=settings.OPENAI_API_KEY, timeout=TIMEOUT_SECONDS, max_retries=0
    )
    try:
        with path.open("rb") as f:
            response = client.audio.transcriptions.create(
                model=MODEL,
                file=f,
                response_format="verbose_json",
                prompt=prompt,
            )
    except Exception as exc:
        soft_limit = _find_soft_limit(exc)
        if soft_limit is not None:
            if soft_limit is exc:
                raise
            raise soft_limit from None
        mapped = _map_error(exc)
        if mapped is None:
            raise
        raise mapped from exc

    raw = response.model_dump()
    segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"]}
        for s in raw.get("segments") or []
    ]
    return WhisperResult(
        text=raw["text"],
        language=raw.get("language", ""),
        duration=raw.get("duration", 0.0),
        segments=segments,
        raw=raw,
    )
