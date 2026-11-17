"""Helpers that build tiny media files for tests with ffmpeg."""

import shutil
import subprocess
import unittest
from pathlib import Path

requires_ffmpeg = unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")


def make_fixture(tmpdir: Path, name: str, *ffmpeg_args: str) -> Path:
    """Run ffmpeg with the given arguments and write the result to tmpdir/name.

    Pass the `-f lavfi -i ...` inputs and the output options in ffmpeg_args.
    The output path is added last.
    """
    out = Path(tmpdir) / name
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *ffmpeg_args, str(out)],
        check=True,
        capture_output=True,
    )
    return out
