"""Helpers that run ffprobe and ffmpeg on lecture recordings."""

import errno
import json
import os
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
