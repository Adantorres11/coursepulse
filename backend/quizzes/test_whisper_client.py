import tempfile
from pathlib import Path
from unittest.mock import Mock

import httpx2
import openai
from celery.exceptions import SoftTimeLimitExceeded
from django.test import SimpleTestCase, override_settings

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
from .whisper_client import WhisperResult, transcribe_chunk

URL = "https://api.openai.com/v1/audio/transcriptions"
KEY = "sk-test"

DUMP = {
    "text": "hi",
    "language": "english",
    "duration": 12.0,
    "segments": [{"id": 0, "start": 0.0, "end": 2.0, "text": "hi", "tokens": [1]}],
}


def status_error(cls, status, body):
    request = httpx2.Request("POST", URL)
    response = httpx2.Response(status, request=request, json=body)
    return cls("failed", response=response, body=body)


def fake_factory(create):
    client = Mock()
    client.audio.transcriptions.create = create
    return Mock(return_value=client)


@override_settings(OPENAI_API_KEY=KEY)
class TranscribeChunkTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "chunk.mp3"
        self.path.write_bytes(b"audio")

    def run_with(self, exc):
        factory = fake_factory(Mock(side_effect=exc))
        return transcribe_chunk(self.path, "p", client_factory=factory)

    def assert_job_error(self, exc, error_class, message):
        with self.assertRaises(error_class) as ctx:
            self.run_with(exc)
        self.assertEqual(ctx.exception.message, message)
        self.assertNotIn(KEY, str(ctx.exception))
        self.assertNotIn(KEY, ctx.exception.message)
        self.assertIs(ctx.exception.__cause__, exc)

    @override_settings(OPENAI_API_KEY="")
    def test_missing_key_fails_without_calling_openai(self):
        factory = Mock()
        with self.assertRaises(PermanentError) as ctx:
            transcribe_chunk(self.path, "p", client_factory=factory)
        self.assertEqual(ctx.exception.message, NO_KEY)
        factory.assert_not_called()

    def test_success_returns_text_language_segments(self):
        response = Mock()
        response.model_dump.return_value = DUMP
        create = Mock(return_value=response)
        factory = fake_factory(create)

        result = transcribe_chunk(self.path, "p", client_factory=factory)

        self.assertIsInstance(result, WhisperResult)
        self.assertEqual(result.text, "hi")
        self.assertEqual(result.language, "english")
        self.assertEqual(result.duration, 12.0)
        self.assertEqual(result.segments, [{"start": 0.0, "end": 2.0, "text": "hi"}])
        self.assertEqual(result.raw, DUMP)
        factory.assert_called_once_with(api_key=KEY, timeout=120.0, max_retries=0)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["model"], "whisper-1")
        self.assertEqual(kwargs["response_format"], "verbose_json")
        self.assertEqual(kwargs["prompt"], "p")
        self.assertIn("file", kwargs)

    def test_invalid_key_is_permanent(self):
        exc = status_error(openai.AuthenticationError, 401, {"code": "invalid_api_key"})
        self.assert_job_error(exc, PermanentError, BAD_KEY)

    def test_permission_denied_is_permanent(self):
        exc = status_error(openai.PermissionDeniedError, 403, {"code": "forbidden"})
        self.assert_job_error(exc, PermanentError, BAD_KEY)

    def test_insufficient_quota_is_permanent(self):
        exc = status_error(openai.RateLimitError, 429, {"code": "insufficient_quota"})
        self.assert_job_error(exc, PermanentError, NO_CREDITS)

    def test_insufficient_quota_type_is_permanent(self):
        body = {"type": "insufficient_quota", "code": None}
        exc = status_error(openai.RateLimitError, 429, body)
        self.assert_job_error(exc, PermanentError, NO_CREDITS)

    def test_credit_balance_exhausted_is_permanent(self):
        body = {"type": "credit_balance_exhausted"}
        exc = status_error(openai.RateLimitError, 429, body)
        self.assert_job_error(exc, PermanentError, NO_CREDITS)

    def test_rate_limit_is_temporary(self):
        body = {"code": "rate_limit_exceeded"}
        exc = status_error(openai.RateLimitError, 429, body)
        self.assert_job_error(exc, TransientError, SERVICE_BUSY)

    def test_server_error_is_temporary(self):
        exc = status_error(openai.InternalServerError, 503, {"code": "overloaded"})
        self.assert_job_error(exc, TransientError, SERVICE_BUSY)

    def test_timeout_is_temporary(self):
        exc = openai.APITimeoutError(request=httpx2.Request("POST", URL))
        self.assert_job_error(exc, TransientError, SERVICE_BUSY)

    def test_connection_drop_is_temporary(self):
        exc = openai.APIConnectionError(request=httpx2.Request("POST", URL))
        self.assert_job_error(exc, TransientError, SERVICE_BUSY)

    def test_bad_audio_is_permanent(self):
        exc = status_error(openai.BadRequestError, 400, {"code": "invalid_audio"})
        self.assert_job_error(exc, PermanentError, UNREADABLE)

    def test_other_status_error_is_unexpected(self):
        exc = status_error(openai.NotFoundError, 404, {"code": "missing"})
        self.assert_job_error(exc, PermanentError, UNEXPECTED)

    def test_soft_time_limit_passes_through(self):
        exc = SoftTimeLimitExceeded()
        with self.assertRaises(SoftTimeLimitExceeded) as ctx:
            self.run_with(exc)
        self.assertIs(ctx.exception, exc)

    def test_soft_time_limit_inside_connection_error(self):
        original = SoftTimeLimitExceeded()
        try:
            try:
                raise original
            except SoftTimeLimitExceeded as cause:
                raise openai.APIConnectionError(
                    request=httpx2.Request("POST", URL)
                ) from cause
        except openai.APIConnectionError as wrapped:
            exc = wrapped
        with self.assertRaises(SoftTimeLimitExceeded) as ctx:
            self.run_with(exc)
        self.assertIs(ctx.exception, original)

    def test_soft_time_limit_in_context_only(self):
        original = SoftTimeLimitExceeded()
        try:
            try:
                raise original
            except SoftTimeLimitExceeded:
                raise openai.APITimeoutError(request=httpx2.Request("POST", URL))
        except openai.APITimeoutError as wrapped:
            exc = wrapped
        with self.assertRaises(SoftTimeLimitExceeded) as ctx:
            self.run_with(exc)
        self.assertIs(ctx.exception, original)
