"""py.utils.ffmpeg — system FFmpeg/ffprobe wrappers.

Nothing ships in git. Homebrew ``ffmpeg`` 9.x on ``ix``. Also: volume
detection so ``py.exec.separate`` can drop mute-mix vocals instead of
keeping a 4 kbps husk.
"""

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


def probe_format(path: Path) -> dict[str, str]:
    """ffprobe format keys (duration, size, bit_rate). Empty dict on failure."""
    completed = subprocess.run(
        [
            ffprobe_bin(),
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {}
    fmt = json.loads(completed.stdout or "{}").get("format") or {}
    return {str(k): str(v) for k, v in fmt.items() if v is not None}


def volume_stats(path: Path) -> tuple[float | None, float | None]:
    """Return (mean_volume_db, max_volume_db) from ffmpeg volumedetect."""
    completed = subprocess.run(
        [
            ffmpeg_bin(),
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    text = (completed.stderr or "") + (completed.stdout or "")
    mean = max_v = None
    for line in text.splitlines():
        if "mean_volume:" in line:
            try:
                mean = float(line.split("mean_volume:")[1].split("dB")[0].strip())
            except ValueError:
                pass
        if "max_volume:" in line:
            try:
                max_v = float(line.split("max_volume:")[1].split("dB")[0].strip())
            except ValueError:
                pass
    return mean, max_v


# ~16 kbps. 95 North mute mix was 4 kbps / 0.2 MB for 7 minutes.
_EMPTY_BYTES_PER_SEC = 2000.0
_EMPTY_MEAN_DB = -50.0
_EMPTY_MAX_DB = -35.0


def is_insignificant_audio(path: Path) -> bool:
    """True when a file is silence / near-silence (no point keeping it)."""
    if not path.is_file() or path.stat().st_size == 0:
        return True
    info = probe_format(path)
    try:
        duration = float(info.get("duration") or 0)
    except ValueError:
        duration = 0.0
    size = path.stat().st_size
    if duration >= 20 and size / duration < _EMPTY_BYTES_PER_SEC:
        return True
    try:
        bitrate = int(info.get("bit_rate") or 0)
    except ValueError:
        bitrate = 0
    if duration >= 20 and 0 < bitrate < 16_000:
        return True
    mean, max_v = volume_stats(path)
    if mean is None or max_v is None:
        return False
    return mean < _EMPTY_MEAN_DB and max_v < _EMPTY_MAX_DB


def encode_aac(src: Path, dest: Path, *, bitrate: str = "256k") -> None:
    run_ffmpeg(["-i", str(src), "-vn", "-c:a", "aac", "-b:a", bitrate, str(dest)])


def encode_silence_aac(dest: Path, duration: float, *, bitrate: str = "64k") -> None:
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            f"{max(duration, 0.1):.3f}",
            "-c:a",
            "aac",
            "-b:a",
            bitrate,
            str(dest),
        ]
    )


def audio_duration(path: Path) -> float:
    info = probe_format(path)
    try:
        return float(info.get("duration") or 0)
    except ValueError:
        return 0.0


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
