#!/usr/bin/env python3
"""Write artist / title from 'Artist - Title' filenames.

Ported from https://github.com/davidrichardnelson/music (tag_updater.py).
Skips files that already have matching tags unless --force.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

from py.base import Job, Tool

TAG_EXTS = {".mp3", ".m4a", ".mp4"}


def parse_artist_title(name: str) -> tuple[str, str] | None:
    stem = Path(name).stem
    if " - " not in stem:
        return None
    artist, title = stem.split(" - ", 1)
    artist, title = artist.strip(), title.strip()
    if not artist or not title:
        return None
    return artist, title


def _read_easy(path: Path) -> tuple[str, str]:
    try:
        audio = MutagenFile(path, easy=True)
        if audio is None or audio.tags is None:
            return "", ""
        artist = audio.tags.get("artist", [""])[0]
        title = audio.tags.get("title", [""])[0]
        return str(artist), str(title)
    except Exception:
        return "", ""


class TagUpdater(Tool):
    """Batch-set artist/title from filenames. MP3 and M4A."""

    def __init__(
        self,
        source: Path,
        dest: Path | None = None,
        *,
        dry_run: bool = True,
        recursive: bool = False,
        force: bool = False,
    ) -> None:
        super().__init__(source, dest, dry_run=dry_run, recursive=recursive)
        self.force = force

    def discover(self) -> list[Path]:
        if self.source.is_file():
            return [self.source] if self.source.suffix.lower() in TAG_EXTS else []
        if not self.source.is_dir():
            return []
        iterator = self.source.rglob("*") if self.recursive else self.source.iterdir()
        return sorted(
            path
            for path in iterator
            if path.is_file() and path.suffix.lower() in TAG_EXTS
        )

    def plan(self) -> list[Job]:
        jobs: list[Job] = []
        for src in self.discover():
            parsed = parse_artist_title(src.name)
            if not parsed:
                jobs.append(Job(src, src, "skip", "filename is not 'Artist - Title'"))
                continue
            artist, title = parsed
            current_artist, current_title = _read_easy(src)
            if (
                not self.force
                and current_artist.strip() == artist
                and current_title.strip() == title
            ):
                jobs.append(Job(src, src, "skip", "tags already match"))
                continue
            jobs.append(
                Job(
                    src,
                    src,
                    "tag",
                    extra={"artist": artist, "title": title},
                )
            )
        return jobs

    def _write(self, path: Path, artist: str, title: str) -> None:
        suffix = path.suffix.lower()
        if suffix == ".mp3":
            audio = MP3(path, ID3=EasyID3)
            if audio.tags is None:
                audio.add_tags()
            audio["artist"] = artist
            audio["title"] = title
            audio.save()
            return
        audio = MutagenFile(path, easy=True)
        if audio is None:
            raise RuntimeError(f"cannot tag {path}")
        if audio.tags is None:
            audio.add_tags()
        audio["artist"] = artist
        audio["title"] = title
        audio.save()

    def run(self) -> list[Job]:
        jobs = self.plan()
        self.print_plan(jobs)
        if self.dry_run:
            return jobs
        for job in jobs:
            if job.action != "tag":
                continue
            self._write(job.source, job.extra["artist"], job.extra["title"])
        return jobs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Set artist/title from 'Artist - Title' filenames. Dry-run by default."
    )
    parser.add_argument("folder", type=Path, nargs="?", default=Path.cwd())
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tool = TagUpdater(
        args.folder,
        dry_run=not args.execute,
        recursive=args.recursive,
        force=args.force,
    )
    tool.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
