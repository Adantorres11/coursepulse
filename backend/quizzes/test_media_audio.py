import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from quizzes import job_errors, media
from quizzes.job_errors import PermanentError
from quizzes.media import Chunk
from quizzes.media_testing import make_fixture, requires_ffmpeg

SINE = ["-f", "lavfi", "-i"]


def _ffprobe(path, *entries):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries[0], "-of", "default=nw=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return dict(line.split("=", 1) for line in out.splitlines())


@requires_ffmpeg
class AudioTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmp = Path(tempfile.mkdtemp())
        cls.gap = make_fixture(
            cls.tmp, "gap.wav",
            *SINE, "sine=f=300:d=20",
            *SINE, "anullsrc=r=44100:cl=mono:d=180",
            *SINE, "sine=f=300:d=20",
            "-filter_complex",
            "[0:a]aresample=44100[a];[1:a]aresample=44100[b];[2:a]aresample=44100[c];"
            "[a][b][c]concat=n=3:v=0:a=1[o]",
            "-map", "[o]", "-ac", "1",
        )
        cls.quiet = make_fixture(
            cls.tmp, "quiet.wav", *SINE, "sine=f=300:d=30,volume=-22dB"
        )
        cls.stereo = make_fixture(
            cls.tmp, "stereo.wav",
            *SINE, "sine=f=300:d=20", *SINE, "anullsrc=r=44100:cl=mono:d=20",
            "-filter_complex", "[0:a][1:a]amerge=inputs=2[o]", "-map", "[o]", "-ac", "2",
        )
        cls.tone = make_fixture(cls.tmp, "tone.wav", *SINE, "sine=f=300:d=35")
        cls.bad = cls.tmp / "bad.wav"
        cls.bad.write_text("this is not audio")

    def test_find_silences_reports_mid_silence(self):
        silences, duration = media.find_silences(self.gap, 0)
        self.assertEqual(len(silences), 1)
        self.assertAlmostEqual(silences[0][0], 20, delta=1)
        self.assertAlmostEqual(silences[0][1], 200, delta=1)
        self.assertAlmostEqual(duration, 220, delta=1)

    def test_find_silences_returns_decoded_duration_when_probe_has_none(self):
        src = self.tmp / "pipe.webm"
        with open(src, "wb") as fh:
            subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *SINE,
                 "sine=f=300:d=30", "-c:a", "libopus", "-f", "webm", "-"],
                stdout=fh, check=True,
            )
        self.assertIsNone(media.probe(src).duration)
        _, duration = media.find_silences(src, 0)
        self.assertAlmostEqual(duration, 30, delta=1)

    def test_quiet_speech_level_is_not_silence(self):
        silences, duration = media.find_silences(self.quiet, 0)
        self.assertEqual(silences, [])
        start, end = media.speech_bounds(duration, silences)
        self.assertAlmostEqual(start, 0, delta=0.1)
        self.assertAlmostEqual(end, 30, delta=1)

    def test_find_silences_uses_minus_50_db(self):
        done = subprocess.CompletedProcess([], 0, b"", b"time=00:00:05.00")
        with mock.patch.object(media, "run_tool", return_value=done) as run:
            media.find_silences(Path("/x/a.wav"), 1)
        args, timeout = run.call_args.args
        self.assertIn("silencedetect=noise=-50dB:d=2", args)
        self.assertEqual(timeout, 600)

    def test_find_silences_closes_unmatched_final_silence(self):
        err = b"silence_start: 4.0\ntime=00:00:09.50\n"
        done = subprocess.CompletedProcess([], 0, b"", err)
        with mock.patch.object(media, "run_tool", return_value=done):
            silences, duration = media.find_silences(Path("/x/a.wav"), 0)
        self.assertEqual(silences, [(4.0, 9.5)])
        self.assertEqual(duration, 9.5)

    def test_speech_bounds_trims_leading_silence_only(self):
        self.assertEqual(media.speech_bounds(300, [(0, 5), (60, 240)]), (5, 300))

    def test_speech_bounds_trims_trailing_silence(self):
        self.assertEqual(media.speech_bounds(300, [(250, 300)]), (0, 250))

    def test_speech_bounds_all_silence_raises_no_speech(self):
        with self.assertRaises(PermanentError) as ctx:
            media.speech_bounds(60, [(0, 60)])
        self.assertEqual(ctx.exception.message, job_errors.NO_SPEECH)

    def test_normalize_outputs_mono_16k_mp3(self):
        dest = self.tmp / "norm.mp3"
        media.normalize_audio(self.stereo, 0, 0, 20, dest)
        info = _ffprobe(dest, "stream=channels,sample_rate,codec_name")
        self.assertEqual(info["channels"], "1")
        self.assertEqual(info["sample_rate"], "16000")
        self.assertEqual(info["codec_name"], "mp3")
        self.assertGreater(dest.stat().st_size, 0)

    def test_normalize_format_does_not_depend_on_name(self):
        dest = self.tmp / "out.bin"
        media.normalize_audio(self.tone, 0, 0, 10, dest)
        self.assertEqual(_ffprobe(dest, "format=format_name")["format_name"], "mp3")

    def test_normalize_handles_emoji_and_quotes_in_name(self):
        src = self.tmp / "lecture 'one' \"two\" \U0001F393 é -x.mp3"
        src.write_bytes(self.tone.read_bytes())
        dest = self.tmp / "emoji-out.mp3"
        media.normalize_audio(src, 0, 0, 10, dest)
        self.assertGreater(dest.stat().st_size, 0)

    def test_normalize_failure_never_leaves_empty_file(self):
        dest = self.tmp / "fail.mp3"
        with self.assertRaises(PermanentError) as ctx:
            media.normalize_audio(self.bad, 0, 0, 10, dest)
        self.assertEqual(ctx.exception.message, job_errors.UNREADABLE)
        self.assertFalse(dest.exists() and dest.stat().st_size == 0)

    def test_cut_chunk_has_expected_length(self):
        norm = self.tmp / "norm35.mp3"
        media.normalize_audio(self.tone, 0, 0, 35, norm)
        dest = self.tmp / "cut.mp3"
        media.cut_chunk(norm, Chunk(1, 10, 22), dest)
        self.assertAlmostEqual(media.probe(dest).duration, 12, delta=0.5)


class PlanChunksTests(SimpleTestCase):
    def test_plan_chunks_single_chunk_when_short(self):
        self.assertEqual(media.plan_chunks(500, []), [Chunk(0, 0, 500)])

    def test_plan_chunks_exact_chunk_seconds_is_one_chunk(self):
        self.assertEqual(media.plan_chunks(600, []), [Chunk(0, 0, 600)])

    def test_plan_chunks_cuts_on_nearby_silence_with_overlap(self):
        chunks = media.plan_chunks(1500, [(590, 596)])
        self.assertEqual(chunks[0].end, 593.0)
        self.assertEqual(chunks[1].start, 591.0)
        self.assertEqual(chunks[1].end, 1193.0)
        self.assertEqual(chunks[-1].end, 1500)
        self.assertEqual([c.index for c in chunks], [0, 1, 2])

    def test_plan_chunks_merges_short_last_chunk(self):
        chunks = media.plan_chunks(1210, [])
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[1], Chunk(1, 598, 1210))

    def test_plan_chunks_is_deterministic(self):
        silences = [(590, 596), (1180, 1190)]
        self.assertEqual(
            media.plan_chunks(3000, silences), media.plan_chunks(3000, silences)
        )

    def test_plan_chunks_never_reuses_an_earlier_silence(self):
        chunks = media.plan_chunks(50, [(8, 12)], chunk_seconds=20)
        self.assertEqual(chunks[0].end, 10.0)
        self.assertEqual(chunks[-1].end, 50)
        ends = [c.end for c in chunks]
        self.assertEqual(ends, sorted(set(ends)))

    def test_plan_chunks_short_chunks_without_silences(self):
        self.assertEqual(
            media.plan_chunks(50, [], chunk_seconds=20),
            [Chunk(0, 0, 20), Chunk(1, 18, 50)],
        )
