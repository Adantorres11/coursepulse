import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from quizzes import job_errors, media
from quizzes.job_errors import PermanentError
from quizzes.media_testing import make_fixture, requires_ffmpeg


def _has_encoder(name):
    if not shutil.which("ffmpeg"):
        return False
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True
    ).stdout
    return name in out


def _completed(returncode=0, stdout=b"", stderr=b""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


@requires_ffmpeg
class ProbeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = Path(tempfile.mkdtemp())
        sine = ["-f", "lavfi", "-i"]
        cls.audio_only = make_fixture(
            cls.tmp, "VIDEO.MP4", *sine, "sine=frequency=440:duration=15", "-c:a", "aac"
        )
        cls.muted = make_fixture(
            cls.tmp, "muted.mp4",
            *sine, "testsrc=duration=2:size=160x120:rate=10", "-c:v", "mpeg4",
        )
        cls.hevc = None
        if _has_encoder("libx265"):
            cls.hevc = make_fixture(
                cls.tmp, "hevc.mp4",
                *sine, "testsrc=duration=2:size=160x120:rate=10",
                *sine, "sine=frequency=440:duration=2",
                "-c:v", "libx265", "-tag:v", "hvc1", "-c:a", "aac", "-vsync", "vfr",
            )
        cls.two_tracks = make_fixture(
            cls.tmp, "tracks.mkv",
            *sine, "testsrc=duration=2:size=160x120:rate=10",
            *sine, "sine=frequency=440:duration=2",
            *sine, "sine=frequency=880:duration=2",
            "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "mpeg4", "-c:a", "aac",
            "-disposition:a:0", "0", "-disposition:a:1", "default",
        )
        cls.emoji = make_fixture(
            cls.tmp, "lecture 'one' \"two\" \U0001F393 é -x.mp3",
            *sine, "sine=frequency=440:duration=3", "-c:a", "libmp3lame",
        )
        cls.truncated = cls.tmp / "truncated.mp4"
        cls.truncated.write_bytes(cls.audio_only.read_bytes()[:2048])
        cls.empty = cls.tmp / "empty.mp4"
        cls.empty.write_bytes(b"")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        super().tearDownClass()

    def test_probe_audio_only_mp4_in_capitals(self):
        info = media.probe(self.audio_only)
        self.assertFalse(info.has_video)
        self.assertEqual(info.audio_index, 0)
        self.assertAlmostEqual(info.duration, 15, delta=1)

    def test_probe_hevc_video_with_audio(self):
        if self.hevc is None:
            self.skipTest("libx265 encoder not available")
        info = media.probe(self.hevc)
        self.assertTrue(info.has_video)
        self.assertIsNotNone(info.audio_index)

    def test_probe_muted_video_raises_no_audio(self):
        with self.assertRaises(PermanentError) as ctx:
            media.probe(self.muted)
        self.assertEqual(ctx.exception.message, job_errors.NO_AUDIO)

    def test_probe_zero_byte_file(self):
        with mock.patch("quizzes.media.subprocess.run") as run:
            with self.assertRaises(PermanentError) as ctx:
                media.probe(self.empty)
        self.assertEqual(ctx.exception.message, job_errors.EMPTY_FILE)
        run.assert_not_called()

    def test_probe_truncated_file_is_unreadable(self):
        with self.assertRaises(PermanentError) as ctx:
            media.probe(self.truncated)
        self.assertEqual(ctx.exception.message, job_errors.UNREADABLE)

    def test_probe_missing_file(self):
        with self.assertRaises(PermanentError) as ctx:
            media.probe(self.tmp / "nope.mp4")
        self.assertEqual(ctx.exception.message, job_errors.FILE_MISSING)

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_probe_unreadable_permissions(self):
        locked = self.tmp / "locked.mp4"
        shutil.copy(self.audio_only, locked)
        locked.chmod(0)
        try:
            with self.assertRaises(PermanentError) as ctx:
                media.probe(locked)
        finally:
            locked.chmod(0o600)
        self.assertEqual(ctx.exception.message, job_errors.FILE_PERMISSION)

    def test_probe_picks_default_audio_track(self):
        info = media.probe(self.two_tracks)
        self.assertEqual(info.audio_index, 2)

    def test_probe_handles_emoji_and_quotes_in_name(self):
        info = media.probe(self.emoji)
        self.assertEqual(info.audio_index, 0)

    def test_disk_full_maps_to_disk_full(self):
        with mock.patch(
            "quizzes.media.subprocess.run",
            return_value=_completed(1, stderr=b"No space left on device"),
        ):
            with self.assertRaises(PermanentError) as ctx:
                media.probe(self.audio_only)
        self.assertEqual(ctx.exception.message, job_errors.DISK_FULL)

    def test_tool_timeout_maps_to_timeout(self):
        with mock.patch(
            "quizzes.media.subprocess.run",
            side_effect=subprocess.TimeoutExpired("ffprobe", 60),
        ):
            with self.assertRaises(PermanentError) as ctx:
                media.probe(self.audio_only)
        self.assertEqual(ctx.exception.message, job_errors.TIMEOUT)

    def test_probe_uses_60_second_timeout(self):
        payload = json.dumps(
            {"format": {"duration": "1.0"}, "streams": [{"index": 0, "codec_type": "audio"}]}
        ).encode()
        with mock.patch(
            "quizzes.media.subprocess.run", return_value=_completed(0, stdout=payload)
        ) as run:
            media.probe(self.audio_only)
        self.assertEqual(run.call_args.kwargs["timeout"], 60)
