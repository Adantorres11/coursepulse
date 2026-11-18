"""Helpers that run ffprobe and ffmpeg on lecture recordings."""

import errno
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import job_errors
from .job_errors import PermanentError

FFPROBE_TIMEOUT = 60
FFMPEG_TIMEOUT = 600


@dataclass(frozen=True)
class MediaInfo:
    duration: float | None
    audio_index: int | None
    has_video: bool


def run_tool(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    """Run ffmpeg or ffprobe and map every failure to a PermanentError.

    subprocess.run kills the process when the timeout passes.
    Other exceptions, such as celery's SoftTimeLimitExceeded, pass through.
    """
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        raise PermanentError(job_errors.TIMEOUT)
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            raise PermanentError(job_errors.DISK_FULL)
        raise
    if result.returncode != 0:
        if b"No space left on device" in (result.stderr or b""):
            raise PermanentError(job_errors.DISK_FULL)
        raise PermanentError(job_errors.UNREADABLE)
    return result


def probe(path: Path) -> MediaInfo:
    path = Path(path)
    if not path.exists():
        raise PermanentError(job_errors.FILE_MISSING)
    if not os.access(path, os.R_OK):
        raise PermanentError(job_errors.FILE_PERMISSION)
    if path.stat().st_size == 0:
        raise PermanentError(job_errors.EMPTY_FILE)

    result = run_tool(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", f"file:{path}",
        ],
        FFPROBE_TIMEOUT,
    )
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise PermanentError(job_errors.UNREADABLE)

    streams = data.get("streams") or []
    if not streams:
        raise PermanentError(job_errors.UNREADABLE)
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    has_video = any(
        s.get("codec_type") == "video"
        and not (s.get("disposition") or {}).get("attached_pic")
        for s in streams
    )
    if not audio:
        raise PermanentError(job_errors.NO_AUDIO if has_video else job_errors.UNREADABLE)
    chosen = next(
        (s for s in audio if (s.get("disposition") or {}).get("default") == 1), audio[0]
    )

    duration = None
    for raw in ((data.get("format") or {}).get("duration"), chosen.get("duration")):
        try:
            duration = float(raw)
            break
        except (TypeError, ValueError):
            continue
    return MediaInfo(duration=duration, audio_index=chosen["index"], has_video=has_video)


@dataclass(frozen=True)
class Chunk:
    index: int
    start: float
    end: float


_SILENCE_START = re.compile(r"silence_start: (-?[\d.]+)")
_SILENCE_END = re.compile(r"silence_end: (-?[\d.]+)")
_TIME = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


def find_silences(path: Path, audio_index: int) -> tuple[list[tuple[float, float]], float]:
    """Return the silent spans and the decoded duration of one audio stream.

    The check runs on the raw audio, before loudnorm, so quiet far-away
    microphones are not mistaken for silence.
    """
    result = run_tool(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-i", f"file:{path}",
            "-map", f"0:{audio_index}", "-af", "silencedetect=noise=-50dB:d=2",
            "-f", "null", "-",
        ],
        FFMPEG_TIMEOUT,
    )
    log = (result.stderr or b"").decode("utf-8", errors="replace")
    times = _TIME.findall(log)
    duration = 0.0
    if times:
        hours, minutes, seconds = times[-1]
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    silences = []
    open_start = None
    for line in log.splitlines():
        start = _SILENCE_START.search(line)
        if start:
            open_start = max(0.0, float(start.group(1)))
            continue
        end = _SILENCE_END.search(line)
        if end and open_start is not None:
            silences.append((open_start, float(end.group(1))))
            open_start = None
    if open_start is not None:
        silences.append((open_start, duration))
    return silences, duration


def speech_bounds(
    duration: float, silences: list[tuple[float, float]]
) -> tuple[float, float]:
    """Trim only leading and trailing silence. Mid silences stay in place."""
    start, end = 0.0, duration
    for s_start, s_end in silences:
        if s_start <= 0.5:
            start = s_end
        if s_end >= duration - 0.5:
            end = s_start
    if start >= end:
        raise PermanentError(job_errors.NO_SPEECH)
    return start, end


def _check_output(dest: Path) -> None:
    if not dest.exists() or dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise PermanentError(job_errors.UNREADABLE)


def normalize_audio(
    src: Path, audio_index: int, start: float, end: float, dest: Path
) -> None:
    """Write mono 16 kHz loudness-normalized MP3 audio for the span start to end."""
    try:
        run_tool(
            [
                "ffmpeg", "-nostdin", "-y", "-ss", str(start), "-to", str(end),
                "-i", f"file:{src}", "-map", f"0:{audio_index}", "-vn", "-ac", "1",
                "-ar", "16000", "-af", "loudnorm", "-c:a", "libmp3lame",
                "-b:a", "32k", "-f", "mp3", f"file:{dest}",
            ],
            FFMPEG_TIMEOUT,
        )
    except PermanentError:
        Path(dest).unlink(missing_ok=True)
        raise
    _check_output(Path(dest))


def plan_chunks(
    duration: float,
    silences: list[tuple[float, float]],
    chunk_seconds: float = 600,
    overlap: float = 2.0,
    search: float = 30.0,
    min_last: float = 30.0,
) -> list[Chunk]:
    """Split the audio into parts of about chunk_seconds, cut at quiet moments.

    Each part starts `overlap` seconds early so no word is lost at a cut.
    The result depends only on the input, so a resumed job gets the same parts.
    """
    midpoints = sorted((a + b) / 2 for a, b in silences)
    cuts = [0.0]
    while True:
        target = cuts[-1] + chunk_seconds
        if target >= duration:
            break
        # Only later silences count, so every cut moves forward.
        near = [
            m for m in midpoints
            if m > cuts[-1] + overlap and abs(m - target) <= search
        ]
        cuts.append(min(near, key=lambda m: (abs(m - target), m)) if near else target)

    spans = []
    for i, cut in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else duration
        spans.append((max(0.0, cut - overlap), end))
    if len(spans) > 1 and spans[-1][1] - spans[-1][0] < min_last:
        last = spans.pop()
        spans[-1] = (spans[-1][0], last[1])
    return [Chunk(i, start, end) for i, (start, end) in enumerate(spans)]


def cut_chunk(src: Path, chunk: Chunk, dest: Path) -> None:
    """Copy one planned part out of the normalized MP3 without re-encoding."""
    try:
        run_tool(
            [
                "ffmpeg", "-nostdin", "-y", "-ss", str(chunk.start),
                "-to", str(chunk.end), "-i", f"file:{src}", "-c", "copy",
                "-f", "mp3", f"file:{dest}",
            ],
            FFMPEG_TIMEOUT,
        )
    except PermanentError:
        Path(dest).unlink(missing_ok=True)
        raise
    _check_output(Path(dest))
