#!/usr/bin/env python3
"""py.tools.simple_mp3 — 320k MP3 for H2O Audio / kitesurf headsets.

Ported from https://github.com/davidrichardnelson/music
(simple_mp3.py + simple_mp3_folder.py). Not the stems_audio catalog.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from py.utils.base import Job, Tool
from py.utils.ffmpeg import run_ffmpeg
from py.utils.paths import SIMPLE_MP3_DIRNAME
from py.utils.runlog import add_log_flags, run_cli

CONVERT_EXTS = {".wav", ".m4a", ".mp3", ".aiff", ".aif", ".flac"}


class SimpleMp3(Tool):
    """Convert audio to 320k MP3, or flatten MP3s into one folder."""

    def __init__(
        self,
        source: Path,
        dest: Path | None = None,
        *,
        dry_run: bool = True,
        recursive: bool = True,
        bitrate: str = "320k",
        per_file_folder: bool = False,
        collect: bool = False,
        force: bool = False,
    ) -> None:
        super().__init__(source, dest, dry_run=dry_run, recursive=recursive)
        self.bitrate = bitrate
        self.per_file_folder = per_file_folder
        self.collect = collect
        self.force = force
        if self.dest is None:
            default_name = SIMPLE_MP3_DIRNAME
            self.dest = (
                self.source if self.source.is_dir() else self.source.parent
            ) / default_name

    def _convert_sources(self) -> list[Path]:
        if self.source.is_file():
            return [self.source] if self.source.suffix.lower() in CONVERT_EXTS else []
        iterator = self.source.rglob("*") if self.recursive else self.source.iterdir()
        out = []
        for path in iterator:
            if not path.is_file():
                continue
            if self.dest in path.parents or path.parent == self.dest:
                continue
            if path.suffix.lower() in CONVERT_EXTS:
                out.append(path)
        return sorted(out)

    def _collect_sources(self) -> list[Path]:
        if self.source.is_file():
            return [self.source] if self.source.suffix.lower() == ".mp3" else []
        iterator = self.source.rglob("*.mp3") if self.recursive else self.source.glob("*.mp3")
        out = []
        for path in iterator:
            if self.dest in path.parents or path.parent == self.dest:
                continue
            out.append(path)
        return sorted(out)

    def _unique_dest(self, name: str) -> Path:
        dest = self.dest / name
        if not dest.exists():
            return dest
        stem = Path(name).stem
        suffix = Path(name).suffix
        n = 1
        while True:
            candidate = self.dest / f"{stem}_{n}{suffix}"
            if not candidate.exists():
                return candidate
            n += 1

    def plan(self) -> list[Job]:
        jobs: list[Job] = []
        if self.collect:
            for src in self._collect_sources():
                dest = self._unique_dest(src.name)
                skip = dest.exists() and dest.name == src.name and not self.force
                # same-name already in dest: treat as duplicate unless force
                existing = self.dest / src.name
                if existing.exists() and not self.force:
                    jobs.append(
                        Job(src, existing, "skip", "mp3 already collected")
                    )
                    continue
                jobs.append(Job(src, dest, "copy"))
            return jobs

        for src in self._convert_sources():
            if self.per_file_folder:
                dest = self.dest / src.stem / f"{src.stem}.mp3"
            else:
                dest = self.dest / f"{src.stem}.mp3"
            if dest.exists() and not self.force:
                jobs.append(Job(src, dest, "skip", "mp3 already exists"))
            else:
                jobs.append(Job(src, dest, "convert"))
        return jobs

    def run(self) -> list[Job]:
        jobs = self.plan()
        self.print_plan(jobs)

        def apply(job: Job) -> dict:
            job.dest.parent.mkdir(parents=True, exist_ok=True)
            if job.action == "copy":
                shutil.copy2(job.source, job.dest)
                return {"handling": "copy"}
            run_ffmpeg(
                [
                    "-i",
                    str(job.source),
                    "-vn",
                    "-acodec",
                    "libmp3lame",
                    "-ab",
                    self.bitrate,
                    "-map_metadata",
                    "0",
                    str(job.dest),
                ],
                dry_run=False,
            )
            return {"handling": "convert"}

        return self.execute_logged(jobs, None if self.dry_run else apply)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert or collect 320k MP3s for the H2O headset. Dry-run by default."
    )
    parser.add_argument("command", choices=("convert", "collect"), nargs="?", default="convert")
    parser.add_argument("--path", type=Path, default=Path.cwd())
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--bitrate", default="320k")
    parser.add_argument("--per-file-folder", action="store_true")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--execute", action="store_true")
    add_log_flags(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tool = SimpleMp3(
        args.path,
        args.dest,
        dry_run=not args.execute,
        recursive=not args.no_recursive,
        bitrate=args.bitrate,
        per_file_folder=args.per_file_folder,
        collect=args.command == "collect",
        force=args.force,
    )
    return run_cli("py.tools.simple_mp3", args, tool)


if __name__ == "__main__":
    raise SystemExit(main())
