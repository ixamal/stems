#!/usr/bin/env python3
"""py.exec.extract_stems — pull drums / bass / other / acapella out of a STEM.

Ported from https://github.com/davidrichardnelson/music (extract_stems.py).

NI stream map: 1 drums, 2 bass, 3 other, 4 acapella (see ``py.utils.extraction``).
Default dest is ``~/Music/stems_audio/{Artist}/{Album}/{Title} - {role}.m4a``.
Dry-run unless ``--execute``. Does not modify the container.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.id3 import TALB, TIT2, TPE1
from mutagen.mp4 import MP4

from py.utils.base import Job, Tool
from py.utils.catalog import StemCatalog, read_tags
from py.utils.ffmpeg import run_ffmpeg
from py.utils.paths import STEMS_AUDIO, STEM_ROLES, container_basename, is_stem_container
from py.utils.runlog import add_log_flags, run_cli


class StemExtractor(Tool):
    """Pull drums / bass / other / acapella out of .stem.m4a or .stem.mp4."""

    def __init__(
        self,
        source: Path,
        dest: Path | None = None,
        *,
        dry_run: bool = True,
        recursive: bool = True,
        fmt: str = "m4a",
        roles: dict[int, str] | None = None,
        include_master: bool = False,
        inplace: bool = False,
        force: bool = False,
    ) -> None:
        super().__init__(source, dest or STEMS_AUDIO, dry_run=dry_run, recursive=recursive)
        self.fmt = fmt.lstrip(".").lower()
        if self.fmt not in {"m4a", "wav"}:
            raise ValueError("fmt must be m4a or wav")
        self.roles = dict(roles or STEM_ROLES)
        if include_master:
            self.roles = {0: "master", **self.roles}
        self.inplace = inplace
        self.force = force
        self.catalog = StemCatalog(None if inplace else self.dest)

    def discover(self) -> list[Path]:
        if self.source.is_file():
            return [self.source] if is_stem_container(self.source) else []
        if not self.source.is_dir():
            return []
        iterator = self.source.rglob("*") if self.recursive else self.source.iterdir()
        found = []
        for path in iterator:
            if path.is_file() and is_stem_container(path):
                found.append(path)
        return sorted(found)

    def _source_meta(self, path: Path) -> tuple[str, str, str]:
        artist, album, title = read_tags(path)
        if title in {"Unknown Title", path.stem}:
            title = container_basename(path)
        return artist, album, title

    def plan(self) -> list[Job]:
        jobs: list[Job] = []
        for src in self.discover():
            artist, album, title = self._source_meta(src)
            for stream_id, role in self.roles.items():
                if self.inplace:
                    dest = src.parent / f"{container_basename(src)} - {role}.{self.fmt}"
                    skip, reason = (dest.exists() and not self.force), (
                        "already next to source" if dest.exists() else ""
                    )
                else:
                    dest = self.catalog.destination(artist, album, title, role, self.fmt)
                    skip, reason = self.catalog.should_skip(
                        dest, artist, album, title, role, force=self.force
                    )
                action = "skip" if skip else "extract"
                jobs.append(
                    Job(
                        source=src,
                        dest=dest,
                        action=action,
                        reason=reason,
                        role=role,
                        stream_id=stream_id,
                        extra={"artist": artist, "album": album, "title": title},
                    )
                )
        return jobs

    def _tag_output(self, dest: Path, title: str, artist: str, album: str, role: str) -> None:
        new_title = f"{title} - {role}"
        try:
            audio = MutagenFile(dest)
            if audio is None:
                return
            if self.fmt == "m4a":
                tagged = MP4(dest)
                tagged["\xa9nam"] = [new_title]
                tagged["\xa9ART"] = [artist]
                tagged["\xa9alb"] = [album]
                tagged.save()
                return
            if audio.tags is None:
                audio.add_tags()
            audio.tags.add(TIT2(encoding=3, text=[new_title]))
            audio.tags.add(TPE1(encoding=3, text=[artist]))
            audio.tags.add(TALB(encoding=3, text=[album]))
            audio.save()
        except Exception as exc:
            print(f"Tagging failed for {dest.name}: {exc}")

    def run(self) -> list[Job]:
        jobs = self.plan()
        self.print_plan(jobs)

        def apply(job: Job) -> dict:
            if job.stream_id is None:
                raise RuntimeError("extract job missing stream_id")
            job.dest.parent.mkdir(parents=True, exist_ok=True)
            args = ["-i", str(job.source), "-map", f"0:a:{job.stream_id}"]
            if self.fmt == "m4a":
                args.extend(["-c", "copy"])
            args.append(str(job.dest))
            run_ffmpeg(args, dry_run=False)
            if self.fmt == "m4a":
                from py.utils.meta import copy_source_tags

                copy_source_tags(job.source, job.dest, title_suffix=job.role)
            else:
                meta = job.extra
                self._tag_output(
                    job.dest,
                    str(meta.get("title") or job.source.stem),
                    str(meta.get("artist") or "Unknown Artist"),
                    str(meta.get("album") or "Unknown Album"),
                    job.role or "stem",
                )
            if not self.inplace:
                self.catalog.note_written(job.dest)
            vocals = "present" if job.role in {"acapella", "vocals"} else "n/a"
            return {"handling": f"extract_{job.role}", "vocals": vocals}

        jobs = self.execute_logged(jobs, None if self.dry_run else apply)
        if self.dry_run:
            return jobs
        if not self.inplace:
            written = [
                {
                    "action": job.action,
                    "source": str(job.source),
                    "dest": str(job.dest),
                    "role": job.role,
                    "reason": job.reason,
                }
                for job in jobs
            ]
            manifest = self.catalog.write_manifest(written)
            new_files = [job.dest for job in jobs if job.action == "extract" and job.dest.exists()]
            if new_files:
                playlist = manifest.with_name("extract_latest.m3u")
                playlist.write_text(
                    "#EXTM3U\n" + "".join(f"{path}\n" for path in new_files)
                )
                print(f"playlist: {playlist}")
            print(f"manifest: {manifest}")
        return jobs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract drums / bass / other / acapella from .stem.m4a or .stem.mp4. "
            "Writes under ~/Music/stems_audio unless --inplace. Dry-run by default."
        )
    )
    parser.add_argument("--path", type=Path, default=Path.cwd(), help="File or folder")
    parser.add_argument(
        "--dest",
        type=Path,
        default=STEMS_AUDIO,
        help="Catalog root (default: ~/Music/stems_audio)",
    )
    parser.add_argument("--wav", action="store_true", help="Write WAV instead of M4A")
    parser.add_argument("--m4a", action="store_true", help="Write M4A (default)")
    parser.add_argument("--acapella", "--vocals", action="store_true", dest="acapella")
    parser.add_argument("--master", action="store_true", help="Also extract stream 0")
    parser.add_argument("--inplace", action="store_true", help="Write next to the container")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--force", action="store_true", help="Overwrite existing dest")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    add_log_flags(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.execute and not args.dry_run and len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        return 1
    roles = {4: "acapella"} if args.acapella else None
    fmt = "wav" if args.wav else "m4a"
    tool = StemExtractor(
        args.path,
        None if args.inplace else args.dest,
        dry_run=not args.execute,
        recursive=not args.no_recursive,
        fmt=fmt,
        roles=roles,
        include_master=args.master,
        inplace=args.inplace,
        force=args.force,
    )
    return run_cli("py.exec.extract_stems", args, tool)


if __name__ == "__main__":
    raise SystemExit(main())
