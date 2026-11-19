from types import SimpleNamespace
from unittest.mock import Mock

import httpx2
import openai
from celery.exceptions import SoftTimeLimitExceeded
from django.test import SimpleTestCase, override_settings

from .job_errors import (
    QUESTIONS_BAD_KEY,
    QUESTIONS_BUSY,
    QUESTIONS_NO_CREDITS,
    QUESTIONS_NO_KEY,
    UNEXPECTED,
    PermanentError,
    TransientError,
)
from .question_client import Reply, Usage, ask, cost_of, estimate_cost

URL = "https://api.openai.com/v1/responses"
KEY = "test-key"
SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}}}


def status_error(cls, status, body):
    request = httpx2.Request("POST", URL)
    response = httpx2.Response(status, request=request, json=body)
    return cls("failed", response=response, body=body)


def make_response(
    status="completed", content_type="output_text", text='{"a": 1}', output_text=None
):
    return SimpleNamespace(
        status=status,
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type=content_type, text=text)],
            )
        ],
        output_text=text if output_text is None else output_text,
        usage=SimpleNamespace(
            input_tokens=1000,
            input_tokens_details=SimpleNamespace(cached_tokens=200),
            output_tokens=500,
        ),
    )


def fake_factory(create):
    client = Mock()
    client.responses.create = create
    return Mock(return_value=client)


@override_settings(
    OPENAI_API_KEY=KEY, QUESTION_MODEL="gpt-6-luna", QUESTION_TIMEOUT_SECONDS=180
)
class AskTests(SimpleTestCase):
    def run_ask(self, create, **overrides):
        factory = fake_factory(create)
        args = dict(
            schema_name="questions",
            schema=SCHEMA,
            instructions="rules",
            user_input="transcript",
            effort="medium",
            max_output_tokens=9000,
            cache_key="lecture-7",
            client_factory=factory,
        )
        args.update(overrides)
        return ask(**args), factory

    def assert_job_error(self, exc, error_class, message):
        with self.assertRaises(error_class) as ctx:
            self.run_ask(Mock(side_effect=exc))
        self.assertEqual(ctx.exception.message, message)
        self.assertNotIn(KEY, str(ctx.exception))
        self.assertIs(ctx.exception.__cause__, exc)

    @override_settings(OPENAI_API_KEY="")
    def test_missing_key_is_permanent(self):
        factory = Mock()
        with self.assertRaises(PermanentError) as ctx:
            self.run_ask(Mock(), client_factory=factory)
        self.assertEqual(ctx.exception.message, QUESTIONS_NO_KEY)
        factory.assert_not_called()

    def test_success_returns_data_and_usage(self):
        reply, _ = self.run_ask(Mock(return_value=make_response()))
        self.assertIsInstance(reply, Reply)
        self.assertEqual(reply.data, {"a": 1})
        self.assertEqual(reply.problem, "")
        self.assertEqual(reply.usage, Usage(1000, 200, 500))

    def test_missing_usage_counts_as_zero(self):
        response = make_response()
        response.usage = None
        with self.assertLogs("quizzes.question_client", "WARNING"):
            reply, _ = self.run_ask(Mock(return_value=response))
        self.assertEqual(reply.usage, Usage(0, 0, 0))
        self.assertEqual(reply.data, {"a": 1})

    def test_missing_cached_details_count_as_zero(self):
        response = make_response()
        response.usage.input_tokens_details = None
        with self.assertLogs("quizzes.question_client", "WARNING"):
            reply, _ = self.run_ask(Mock(return_value=response))
        self.assertEqual(reply.usage, Usage(1000, 0, 500))

    def test_missing_output_text_is_bad_json(self):
        reply, _ = self.run_ask(Mock(return_value=make_response(text=None)))
        self.assertIsNone(reply.data)
        self.assertEqual(reply.problem, "bad_json")

    def test_request_shape(self):
        create = Mock(return_value=make_response())
        _, factory = self.run_ask(create)
        factory.assert_called_once_with(api_key=KEY, timeout=180, max_retries=0)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-6-luna")
        self.assertIs(kwargs["store"], False)
        self.assertEqual(kwargs["reasoning"], {"effort": "medium"})
        self.assertEqual(kwargs["max_output_tokens"], 9000)
        self.assertEqual(kwargs["prompt_cache_key"], "lecture-7")
        self.assertEqual(kwargs["instructions"], "rules")
        self.assertEqual(kwargs["input"], "transcript")
        self.assertEqual(
            kwargs["text"],
            {
                "format": {
                    "type": "json_schema",
                    "name": "questions",
                    "schema": SCHEMA,
                    "strict": True,
                }
            },
        )

    def test_incomplete_reply(self):
        reply, _ = self.run_ask(Mock(return_value=make_response(status="incomplete")))
        self.assertEqual(reply.problem, "incomplete")
        self.assertIsNone(reply.data)
        self.assertEqual(reply.usage, Usage(1000, 200, 500))

    def test_refusal_reply(self):
        response = make_response(content_type="refusal", text="no", output_text="")
        reply, _ = self.run_ask(Mock(return_value=response))
        self.assertEqual(reply.problem, "refusal")
        self.assertIsNone(reply.data)

    def test_bad_json_reply(self):
        for text in ("not json", "[1]"):
            with self.subTest(text=text):
                reply, _ = self.run_ask(Mock(return_value=make_response(text=text)))
                self.assertEqual(reply.problem, "bad_json")
                self.assertIsNone(reply.data)

    def test_error_mapping(self):
        request = httpx2.Request("POST", URL)
        cases = [
            (status_error(openai.AuthenticationError, 401, {"code": "x"}),
             PermanentError, QUESTIONS_BAD_KEY),
            (status_error(openai.PermissionDeniedError, 403, {"code": "x"}),
             PermanentError, QUESTIONS_BAD_KEY),
            (status_error(openai.RateLimitError, 429, {"code": "insufficient_quota"}),
             PermanentError, QUESTIONS_NO_CREDITS),
            (status_error(openai.RateLimitError, 429, {"code": "rate_limit_exceeded"}),
             TransientError, QUESTIONS_BUSY),
            (status_error(openai.InternalServerError, 500, {"code": "x"}),
             TransientError, QUESTIONS_BUSY),
            (openai.APITimeoutError(request=request), TransientError, QUESTIONS_BUSY),
            (openai.APIConnectionError(request=request), TransientError, QUESTIONS_BUSY),
            (status_error(openai.BadRequestError, 400, {"code": "x"}),
             PermanentError, UNEXPECTED),
        ]
        for exc, error_class, message in cases:
            with self.subTest(exc=type(exc).__name__, message=message):
                self.assert_job_error(exc, error_class, message)

    def test_soft_time_limit_passes_through(self):
        exc = SoftTimeLimitExceeded()
        with self.assertRaises(SoftTimeLimitExceeded) as ctx:
            self.run_ask(Mock(side_effect=exc))
        self.assertIs(ctx.exception, exc)


class CostTests(SimpleTestCase):
    def test_cost_of(self):
        self.assertAlmostEqual(cost_of(Usage(1_000_000, 0, 1_000_000), "gpt-6-luna"), 0.60)
        self.assertAlmostEqual(
            cost_of(Usage(1_000_000, 1_000_000, 0), "gpt-6-luna"), 0.01
        )

    def test_unknown_model_uses_highest_price(self):
        with self.assertLogs("quizzes.question_client", "WARNING"):
            cost = cost_of(Usage(1_000_000, 0, 0), "mystery")
        self.assertAlmostEqual(cost, 1.00)

    def test_estimate_cost(self):
        self.assertAlmostEqual(estimate_cost(4_000_000, 0, "gpt-6-luna"), 0.10)
