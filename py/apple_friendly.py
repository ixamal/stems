#!/usr/bin/env python3
"""Make files Apple-friendly without touching the Music.app library.

Ported from https://github.com/davidrichardnelson/music
(convert_to_apple_friendly.py).

Video: H.264 + AAC MP4.
Audio: AAC M4A for later Apple Music import if David wants it.
Never writes into ~/Music/Music/Media.localized — that tree is music_migration.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from py.base import Job, Tool
from py.ffmpeg import run_ffmpeg
from py.paths import APPLE_MUSIC_MEDIA

VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
AUDIO_EXTS = {".wav", ".aiff", ".aif", ".flac", ".mp3", ".m4a"}


class AppleFriendly(Tool):
    """Convert video or audio into Apple-friendly containers."""

    def __init__(
        self,
        source: Path,
        dest: Path | None = None,
        *,
        dry_run: bool = True,
        recursive: bool = False,
        mode: str = "auto",
        force: bool = False,
    ) -> None:
        default_dest = (source if source.is_dir() else source.parent) / "ip"
        super().__init__(
            source,
            dest or default_dest,
            dry_run=dry_run,
            recursive=recursive,
        )
        if mode not in {"auto", "video", "audio"}:
            raise ValueError("mode must be auto, video, or audio")
        self.mode = mode
        self.force = force
        if self.dest and (
            self.dest == APPLE_MUSIC_MEDIA or APPLE_MUSIC_MEDIA in self.dest.parents
        ):
            raise ValueError(
                "Refusing to write into Apple Music Media.localized. "
                "Keep stems and conversions out of that catalog."
            )

    def _wanted(self, path: Path) -> str | None:
        suffix = path.suffix.lower()
        if self.mode in {"auto", "video"} and suffix in VIDEO_EXTS:
            if suffix == ".mp4" and path.name.lower().endswith(".ip.mp4"):
                return None
            return "video"
        if self.mode in {"auto", "audio"} and suffix in AUDIO_EXTS:
            if suffix == ".m4a" and self.mode != "audio":
                return None
            return "audio"
        return None

    def discover(self) -> list[tuple[Path, str]]:
        if self.source.is_file():
            kind = self._wanted(self.source)
            return [(self.source, kind)] if kind else []
        if not self.source.is_dir():
            return []
        iterator = self.source.rglob("*") if self.recursive else self.source.iterdir()
        found: list[tuple[Path, str]] = []
        for path in iterator:
            if not path.is_file():
                continue
            if self.dest and (self.dest in path.parents or path.parent == self.dest):
                continue
            kind = self._wanted(path)
            if kind:
                found.append((path, kind))
        return sorted(found, key=lambda item: item[0])

    def plan(self) -> list[Job]:
        jobs: list[Job] = []
        assert self.dest is not None
        for src, kind in self.discover():
            if kind == "video":
                dest = self.dest / f"{src.stem}.ip.mp4"
            else:
                dest = self.dest / f"{src.stem}.m4a"
            if dest.exists() and not self.force:
                jobs.append(Job(src, dest, "skip", "already converted", extra={"kind": kind}))
            else:
                jobs.append(Job(src, dest, "convert", extra={"kind": kind}))
        return jobs

    def run(self) -> list[Job]:
        jobs = self.plan()
        self.print_plan(jobs)
        if self.dry_run:
            return jobs
        assert self.dest is not None
        self.dest.mkdir(parents=True, exist_ok=True)
        for job in jobs:
            if job.action != "convert":
                continue
            kind = job.extra.get("kind")
            if kind == "video":
                run_ffmpeg(
                    [
                        "-i",
                        str(job.source),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-profile:v",
                        "main",
                        "-c:a",
                        "aac",
                        "-movflags",
                        "+faststart",
                        str(job.dest),
                    ],
                    dry_run=False,
                )
            else:
                run_ffmpeg(
                    [
                        "-i",
                        str(job.source),
                        "-vn",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "256k",
                        "-movflags",
                        "+faststart",
                        "-map_metadata",
                        "0",
                        str(job.dest),
                    ],
                    dry_run=False,
                )
        return jobs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert video/audio to Apple-friendly files. "
            "Does not write into Music.app. Dry-run by default."
        )
    )
    parser.add_argument("--path", type=Path, default=Path.cwd())
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--mode", choices=("auto", "video", "audio"), default="auto")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tool = AppleFriendly(
        args.path,
        args.dest,
        dry_run=not args.execute,
        recursive=args.recursive,
        mode=args.mode,
        force=args.force,
    )
    tool.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
