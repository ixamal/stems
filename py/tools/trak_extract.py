#!/usr/bin/env python3
"""py.tools.trak_extract — unpack Traktor ``.trak`` archives into a folder + M3U.

Ported from https://github.com/davidrichardnelson/music (trak_extract.py).
Skips a set if its output folder already has the playlist unless ``--force``.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from py.utils.base import Job, Tool
from py.utils.runlog import add_log_flags, run_cli

AUDIO_EXTS = {".wav", ".aif", ".aiff", ".mp3", ".flac", ".m4a"}


class TrakExtractor(Tool):
    """Unzip .trak files the same way the old utility did."""

    def __init__(
        self,
        source: Path,
        dest: Path | None = None,
        *,
        dry_run: bool = True,
        recursive: bool = False,
        force: bool = False,
    ) -> None:
        default_dest = (
            source if source.is_dir() else source.parent
        ) / "Extracted_Sets"
        super().__init__(
            source,
            dest or default_dest,
            dry_run=dry_run,
            recursive=recursive,
        )
        self.force = force

    def discover(self) -> list[Path]:
        if self.source.is_file():
            return [self.source] if self.source.suffix.lower() == ".trak" else []
        if not self.source.is_dir():
            return []
        iterator = self.source.rglob("*.trak") if self.recursive else self.source.glob("*.trak")
        return sorted(path for path in iterator if path.is_file())

    def plan(self) -> list[Job]:
        jobs: list[Job] = []
        assert self.dest is not None
        for src in self.discover():
            dest = self.dest / src.stem
            playlist = dest / f"{src.stem}.m3u"
            if playlist.exists() and not self.force:
                jobs.append(Job(src, dest, "skip", "set already extracted"))
            else:
                jobs.append(Job(src, dest, "extract"))
        return jobs

    def _unzip(self, trak: Path, temp_dir: Path) -> None:
        completed = subprocess.run(
            ["unzip", "-q", str(trak), "-d", str(temp_dir)],
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"unzip failed for {trak.name}")

    def run(self) -> list[Job]:
        jobs = self.plan()
        self.print_plan(jobs)

        def apply(job: Job) -> dict:
            assert self.dest is not None
            self.dest.mkdir(parents=True, exist_ok=True)
            if job.dest.exists() and self.force:
                shutil.rmtree(job.dest)
            job.dest.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=f"trak_{job.source.stem}_") as tmp:
                temp = Path(tmp)
                self._unzip(job.source, temp)
                names: list[str] = []
                for path in temp.rglob("*"):
                    if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
                        target = job.dest / path.name
                        if target.exists() and not self.force:
                            names.append(path.name)
                            continue
                        shutil.copy2(path, target)
                        names.append(path.name)
                if names:
                    playlist = job.dest / f"{job.source.stem}.m3u"
                    lines = ["#EXTM3U\n"] + [f"{name}\n" for name in names]
                    playlist.write_text("".join(lines))
                    return {"handling": "extract_trak", "has_audio": True}
                print(f"No audio files found in {job.source.name}")
                return {
                    "handling": "extract_trak_empty",
                    "has_audio": False,
                }

        return self.execute_logged(jobs, None if self.dry_run else apply)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract Traktor .trak archives to folders + M3U. Dry-run by default."
    )
    parser.add_argument("input_folder", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--execute", action="store_true")
    add_log_flags(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tool = TrakExtractor(
        args.input_folder,
        args.output,
        dry_run=not args.execute,
        recursive=args.recursive,
        force=args.force,
    )
    return run_cli("py.tools.trak_extract", args, tool)


if __name__ == "__main__":
    raise SystemExit(main())
