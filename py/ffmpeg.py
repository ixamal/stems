"""Thin FFmpeg runner. System binary only — nothing ships in git."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise FFmpegError(
            "ffmpeg not found. Install with Homebrew: brew install ffmpeg"
        )
    return path


def run_ffmpeg(args: list[str], *, dry_run: bool = False) -> None:
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", *args]
    if dry_run:
        return
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        raise FFmpegError(f"ffmpeg failed ({completed.returncode}): {' '.join(cmd)}")


def ffprobe_bin() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise FFmpegError("ffprobe not found (comes with ffmpeg)")
    return path


def audio_stream_codecs(path: Path) -> list[str]:
    """Codec name per audio stream, in file order (0 = master on NI STEM)."""
    completed = subprocess.run(
        [
            ffprobe_bin(),
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise FFmpegError(f"ffprobe failed for {path}")
    streams = json.loads(completed.stdout or "{}").get("streams") or []
    return [str(s.get("codec_name") or "") for s in streams]
