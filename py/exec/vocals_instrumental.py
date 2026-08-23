#!/usr/bin/env python3
"""Vocals + instrumental parallel to each STEM; queue the rest for NUO-STEMS.

The .stem.m4a stays untouched for Traktor Native.

Where a STEM exists, write siblings as AAC:
  {name} - vocals.m4a         stream 4 (copy when already AAC)
  {name} - instrumental.m4a   mix of drums+bass+other (no vocals)

Rekordbox gets those two regular files. Traktor keeps the four-stem container.

Where no STEM sibling exists: append the source track to ``m3u/nuo_queue.m3u``.
That list is for ``py.exec.separate`` (35k+ crate). NUO-STEMS has no CLI and
rejects ``.m3u`` drops. JSON notes stay under ``config/``.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from mutagen.mp4 import MP4

from py.utils.base import Job, Tool
from py.utils.catalog import StemCatalog, read_tags, role_from_name
from py.utils.ffmpeg import FFmpegError, audio_stream_codecs, run_ffmpeg
from py.utils.runlog import add_log_flags, run_cli
from py.utils.paths import (
    CONFIG_DIR,
    M3U_DIR,
    PAIR_ROLES,
    SOURCE_TRACK_EXTS,
    STEMS_AUDIO,
    container_basename,
    ensure_config_dir,
    ensure_m3u_dir,
    is_stem_container,
    sibling_stem,
    skip_tree,
)

ACAPELLA_STREAM = 4
INSTRUMENTAL_STREAMS = (1, 2, 3)
NUO_QUEUE_NAME = "nuo_queue.m3u"


class VocalsInstrumental(Tool):
    """Extract the DJ pair, or queue the track for NUO."""

    def __init__(
        self,
        source: Path,
        dest: Path | None = None,
        *,
        dry_run: bool = True,
        recursive: bool = True,
        inplace: bool = True,
        force: bool = False,
        extract_only: bool = False,
        queue_only: bool = False,
        limit: int | None = None,
        mix_codec: str = "aac",
    ) -> None:
        super().__init__(source, dest or STEMS_AUDIO, dry_run=dry_run, recursive=recursive)
        if mix_codec not in {"alac", "aac"}:
            raise ValueError("mix_codec must be alac or aac")
        self.inplace = inplace
        self.force = force
        self.extract_only = extract_only
        self.queue_only = queue_only
        self.limit = limit
        self.mix_codec = mix_codec
        self.catalog = StemCatalog(None if inplace else self.dest)
        self.queue_path = M3U_DIR / NUO_QUEUE_NAME

    def _iter_files(self):
        if self.source.is_file():
            yield self.source
            return
        if not self.source.is_dir():
            return
        iterator = self.source.rglob("*") if self.recursive else self.source.iterdir()
        for path in iterator:
            if not path.is_file() or path.name.startswith("."):
                continue
            if skip_tree(path):
                continue
            yield path

    def discover_stems(self) -> list[Path]:
        return sorted(p for p in self._iter_files() if is_stem_container(p))

    def discover_needs_stem(self, stem_bases: set[str]) -> list[Path]:
        found = []
        for path in self._iter_files():
            if is_stem_container(path):
                continue
            if path.suffix.lower() not in SOURCE_TRACK_EXTS:
                continue
            if role_from_name(path.name):
                continue
            if path.stem.casefold() in stem_bases:
                continue
            if sibling_stem(path):
                continue
            found.append(path)
        return sorted(found)

    def _meta(self, path: Path) -> tuple[str, str, str]:
        artist, album, title = read_tags(path)
        if title in {"Unknown Title", path.stem}:
            title = container_basename(path) if is_stem_container(path) else path.stem
        return artist, album, title

    def _dest_for(self, src: Path, artist: str, album: str, title: str, role: str) -> Path:
        if self.inplace:
            base = container_basename(src) if is_stem_container(src) else src.stem
            return src.parent / f"{base} - {role}.m4a"
        return self.catalog.destination(artist, album, title, role, "m4a")

    def _pair_already_present(self, src: Path, role: str) -> Path | None:
        """Skip if a same-track vocals/instrumental sibling already exists."""
        base = container_basename(src) if is_stem_container(src) else src.stem
        if role == "vocals":
            labels = ("vocals", "acapella", "vocal")
        else:
            labels = ("instrumental",)
        for label in labels:
            for ext in (".m4a", ".mp3", ".aac"):
                for name in (
                    f"{base} - {label}{ext}",
                    f"{base} ({label}){ext}",
                    f"{base}_{label}{ext}",
                ):
                    candidate = src.parent / name
                    if candidate.exists() and candidate.stat().st_size > 0:
                        return candidate
        return None

    def plan(self) -> list[Job]:
        jobs: list[Job] = []
        stems = [] if self.queue_only else self.discover_stems()
        stem_bases = {container_basename(p).casefold() for p in self.discover_stems()}
        claimed: set[str] = set()
        extracts = 0
        for src in stems:
            if self.limit is not None and extracts >= self.limit:
                break
            artist, album, title = self._meta(src)
            pair_jobs = []
            for role in PAIR_ROLES:
                dest = self._dest_for(src, artist, album, title, role)
                dest_key = str(dest).casefold()
                existing = self._pair_already_present(src, role)
                if dest_key in claimed and not self.force:
                    skip, reason = True, "same dest already planned"
                elif existing and not self.force:
                    skip, reason = True, f"already parallel ({existing.name})"
                elif self.inplace:
                    skip, reason = dest.exists() and not self.force, (
                        "already next to source" if dest.exists() else ""
                    )
                else:
                    skip, reason = self.catalog.should_skip(
                        dest, artist, album, title, role, force=self.force
                    )
                if not skip:
                    claimed.add(dest_key)
                pair_jobs.append(
                    Job(
                        source=src,
                        dest=dest,
                        action="skip" if skip else "extract",
                        reason=reason,
                        role=role,
                        extra={"artist": artist, "album": album, "title": title},
                    )
                )
            jobs.extend(pair_jobs)
            if any(job.action == "extract" for job in pair_jobs):
                extracts += 1

        if not self.extract_only:
            for src in self.discover_needs_stem(stem_bases):
                jobs.append(
                    Job(
                        source=src,
                        dest=self.queue_path,
                        action="queue",
                        reason="no .stem.m4a sibling — NUO Native",
                    )
                )
        return jobs

    def _tag(self, dest: Path, title: str, artist: str, album: str, role: str) -> None:
        try:
            tagged = MP4(dest)
            tagged["\xa9nam"] = [f"{title} - {role}"]
            tagged["\xa9ART"] = [artist]
            tagged["\xa9alb"] = [album]
            tagged.save()
        except Exception as exc:
            print(f"Tagging failed for {dest.name}: {exc}")

    def _extract_acapella(self, src: Path, dest: Path) -> None:
        codecs = audio_stream_codecs(src)
        if len(codecs) < 5:
            raise FFmpegError(f"{src.name} has {len(codecs)} audio streams; need 5")
        args = ["-i", str(src), "-map", f"0:a:{ACAPELLA_STREAM}", "-vn"]
        if codecs[ACAPELLA_STREAM] == "aac":
            args.extend(["-c:a", "copy"])
        else:
            args.extend(["-c:a", self.mix_codec])
        args.append(str(dest))
        run_ffmpeg(args)

    def _extract_instrumental(self, src: Path, dest: Path) -> None:
        codecs = audio_stream_codecs(src)
        if len(codecs) < 4:
            raise FFmpegError(f"{src.name} has {len(codecs)} audio streams; need drums/bass/other")
        labels = "".join(f"[0:a:{i}]" for i in INSTRUMENTAL_STREAMS)
        mix = (
            f"{labels}amix=inputs={len(INSTRUMENTAL_STREAMS)}"
            ":duration=longest:normalize=1[mix]"
        )
        args = [
            "-i",
            str(src),
            "-filter_complex",
            mix,
            "-map",
            "[mix]",
            "-vn",
            "-c:a",
            self.mix_codec,
        ]
        if self.mix_codec == "aac":
            args.extend(["-b:a", "256k", "-movflags", "+faststart"])
        args.append(str(dest))
        run_ffmpeg(args)

    def _write_queue(self, jobs: list[Job]) -> None:
        queued = [job.source for job in jobs if job.action == "queue"]
        ensure_m3u_dir()
        ensure_config_dir()
        lines = ["#EXTM3U\n"] + [f"{path}\n" for path in queued]
        self.queue_path.write_text("".join(lines))
        listing = self.queue_path.with_suffix(".txt")
        listing.write_text("".join(f"{path}\n" for path in queued))
        manifest = {
            "written_at": datetime.now(timezone.utc).isoformat(),
            "count": len(queued),
            "note": "Drag nuo_queue.m3u into NUO-STEMS 4. Mode stays Traktor Pro 4 Native.",
        }
        (CONFIG_DIR / "nuo_queue.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"NUO queue: {self.queue_path} ({len(queued)} tracks)")

    def run(self) -> list[Job]:
        jobs = self.plan()
        extracts = [j for j in jobs if j.action == "extract"]
        skips = [j for j in jobs if j.action == "skip"]
        queued = [j for j in jobs if j.action == "queue"]
        mode = "dry-run" if self.dry_run else "execute"
        print(
            f"{mode}: {len(extracts)} extract / {len(skips)} skip / "
            f"{len(queued)} queue-NUO / {len(jobs)} total",
            flush=True,
        )
        if self.dry_run:
            for job in extracts[:20]:
                print(job.describe())
            if len(extracts) > 20:
                print(f"  … {len(extracts) - 20} more extracts")
            if queued:
                print(f"queue ({len(queued)}) → {self.queue_path}")
            return self.execute_logged(jobs, None)

        def apply(job: Job) -> dict:
            job.dest.parent.mkdir(parents=True, exist_ok=True)
            if job.role == "vocals":
                self._extract_acapella(job.source, job.dest)
            elif job.role == "instrumental":
                self._extract_instrumental(job.source, job.dest)
            else:
                raise RuntimeError(f"unexpected role {job.role}")
            meta = job.extra
            self._tag(
                job.dest,
                str(meta.get("title") or job.source.stem),
                str(meta.get("artist") or "Unknown Artist"),
                str(meta.get("album") or "Unknown Album"),
                job.role,
            )
            if not self.inplace:
                self.catalog.note_written(job.dest)
            from py.utils.meta import copy_source_tags

            copy_source_tags(
                job.source,
                job.dest,
                title_suffix=job.role,
            )
            if job.role == "vocals":
                return {"vocals": "present", "handling": "wrote_vocals"}
            return {"instrumental": "kept", "handling": "wrote_instrumental"}

        jobs = self.execute_logged(jobs, apply)
        if queued:
            self._write_queue(jobs)
        return jobs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Leave .stem.m4a for Traktor. Write parallel AAC vocals + instrumental "
            "for Rekordbox. Queue tracks with no STEM for NUO. Dry-run by default."
        )
    )
    parser.add_argument("--path", type=Path, default=STEMS_AUDIO)
    parser.add_argument("--dest", type=Path, default=STEMS_AUDIO)
    parser.add_argument(
        "--catalog",
        action="store_true",
        help="Write into Artist/Album via tags instead of next to the STEM",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--queue-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Max STEM files to extract")
    parser.add_argument("--alac", action="store_true", help="Encode the mix as ALAC instead of AAC")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--execute", action="store_true")
    add_log_flags(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tool = VocalsInstrumental(
        args.path,
        args.dest,
        dry_run=not args.execute,
        recursive=not args.no_recursive,
        inplace=not args.catalog,
        force=args.force,
        extract_only=args.extract_only,
        queue_only=args.queue_only,
        limit=args.limit,
        mix_codec="alac" if args.alac else "aac",
    )
    return run_cli("py.exec.vocals_instrumental", args, tool)


if __name__ == "__main__":
    raise SystemExit(main())
