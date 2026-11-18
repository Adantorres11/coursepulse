"""One call to the OpenAI Responses API for question generation, with errors mapped to job errors."""

import json
import logging
from dataclasses import dataclass

from django.conf import settings
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from .job_errors import (
    QUESTIONS_BAD_KEY,
    QUESTIONS_BUSY,
    QUESTIONS_NO_CREDITS,
    QUESTIONS_NO_KEY,
    UNEXPECTED,
    PermanentError,
    TransientError,
)
from .whisper_client import _find_soft_limit, _is_out_of_credits

logger = logging.getLogger(__name__)

# Model -> (input, cached input, output) in US dollars per 1M tokens.
PRICES = {
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-6.1-terra": (1.00, 0.05, 5.00),
}
CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cached_tokens: int
    output_tokens: int  # includes reasoning tokens


@dataclass(frozen=True)
class Reply:
    data: dict | None  # None when problem is not empty
    usage: Usage
    problem: str  # "", "refusal", "incomplete", "bad_json"


def _price_of(model):
    price = PRICES.get(model)
    if price is None:
        logger.warning("No price for model %s. Using the highest known price.", model)
        price = max(PRICES.values())
    return price


def cost_of(usage: Usage, model: str) -> float:
    price_in, price_cached, price_out = _price_of(model)
    fresh = usage.input_tokens - usage.cached_tokens
    return (
        fresh * price_in + usage.cached_tokens * price_cached + usage.output_tokens * price_out
    ) / 1_000_000


def estimate_cost(input_chars: int, max_output_tokens: int, model: str) -> float:
    input_tokens = input_chars / CHARS_PER_TOKEN
    price_in, _, price_out = _price_of(model)
    return (input_tokens * price_in + max_output_tokens * price_out) / 1_000_000


def _map_error(exc):
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return PermanentError(QUESTIONS_BAD_KEY)
    if isinstance(exc, RateLimitError):
        if _is_out_of_credits(exc):
            return PermanentError(QUESTIONS_NO_CREDITS)
        return TransientError(QUESTIONS_BUSY)
    if isinstance(exc, (APITimeoutError, APIConnectionError, InternalServerError)):
        return TransientError(QUESTIONS_BUSY)
    if isinstance(exc, APIStatusError):
        return PermanentError(UNEXPECTED)
    return None


def _usage_of(response):
    usage = response.usage
    return Usage(
        input_tokens=usage.input_tokens,
        cached_tokens=usage.input_tokens_details.cached_tokens,
        output_tokens=usage.output_tokens,
    )


def _has_refusal(response):
    return any(
        part.type == "refusal"
        for item in response.output
        if item.type == "message"
        for part in item.content
    )


def ask(
    *,
    schema_name: str,
    schema: dict,
    instructions: str,
    user_input: str,
    effort: str,
    max_output_tokens: int,
    cache_key: str,
    client_factory=OpenAI,
) -> Reply:
    if not settings.OPENAI_API_KEY:
        raise PermanentError(QUESTIONS_NO_KEY)
    client = client_factory(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.QUESTION_TIMEOUT_SECONDS,
        max_retries=0,
    )
    try:
        response = client.responses.create(
            model=settings.QUESTION_MODEL,
            instructions=instructions,
            input=user_input,
            store=False,
            reasoning={"effort": effort},
            max_output_tokens=max_output_tokens,
            prompt_cache_key=cache_key,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
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

    usage = _usage_of(response)
    if response.status == "incomplete":
        return Reply(None, usage, "incomplete")
    if _has_refusal(response):
        return Reply(None, usage, "refusal")
    try:
        data = json.loads(response.output_text)
    except ValueError:
        return Reply(None, usage, "bad_json")
    if not isinstance(data, dict):
        return Reply(None, usage, "bad_json")
    return Reply(data, usage, "")
