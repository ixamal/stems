#!/usr/bin/env python3
"""py.exec.validate_meta — QA that generated files carry source tags.

Traktor / Rekordbox / Music.app read artist, label, BPM, key, cover, and
title from the file. This module compares each source against its
``{name} - vocals.m4a``, ``{name} - instrumental.m4a`` (or acapella), and
``{name}.stem.m4a`` siblings.

Dry-run (default): report mismatches.
``--execute``: copy tags from the source onto those siblings (fix-up).

Also runs at the end of ``py.exec.separate`` after a write. Does not touch
``collection.nml`` or Rekordbox ``master.db``. After a fix, reload tags in
Traktor (file tags, not the NML cache).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from py.exec.vocals_instrumental import VocalsInstrumental
from py.utils.base import Job, Tool
from py.utils.catalog import role_from_name
from py.utils.meta import compare_tags, copy_source_tags
from py.utils.paths import (
    M3U_DIR,
    SOURCE_TRACK_EXTS,
    STEMS_AUDIO,
    container_basename,
    is_stem_container,
    sibling_stem,
    skip_tree,
)
from py.utils.runlog import add_log_flags, run_cli

DEFAULT_QUEUE = M3U_DIR / "nuo_queue_known.m3u"


class MetaValidator(Tool):
    """Compare or repair tags on generated siblings."""

    def __init__(
        self,
        source: Path,
        *,
        dry_run: bool = True,
        recursive: bool = True,
        repair: bool = False,
    ) -> None:
        super().__init__(source, STEMS_AUDIO, dry_run=dry_run, recursive=recursive)
        self.repair = repair
        self._skipper = VocalsInstrumental(
            source if source.is_dir() else source.parent,
            dry_run=True,
            extract_only=True,
        )

    def _iter_tracks(self) -> list[Path]:
        src = self.source
        if src.is_file() and src.suffix.lower() in {".m3u", ".m3u8"}:
            tracks = []
            for line in src.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                path = Path(line).expanduser()
                if path.is_file():
                    tracks.append(path)
            return tracks
        if src.is_file() and src.suffix.lower() in SOURCE_TRACK_EXTS:
            return [src]
        if not src.is_dir():
            return []
        found: list[Path] = []
        stems: list[Path] = []
        iterator = src.rglob("*") if self.recursive else src.iterdir()
        for path in iterator:
            if not path.is_file() or path.name.startswith("."):
                continue
            if skip_tree(path):
                continue
            if is_stem_container(path):
                stems.append(path)
                continue
            if path.suffix.lower() not in SOURCE_TRACK_EXTS:
                continue
            if role_from_name(path.name):
                continue
            found.append(path)
        mix_bases = {path.stem.casefold() for path in found}
        for stem in stems:
            if container_basename(stem).casefold() not in mix_bases:
                found.append(stem)
        return sorted(found)

    def _siblings(self, src: Path) -> list[tuple[Path, str | None]]:
        found: list[tuple[Path, str | None]] = []
        vocals = self._skipper._pair_already_present(src, "vocals")
        instrumental = self._skipper._pair_already_present(src, "instrumental")
        if vocals:
            suffix = "vocals" if "vocal" in vocals.stem.lower() else "acapella"
            found.append((vocals, suffix))
        if instrumental:
            found.append((instrumental, "instrumental"))
        if not is_stem_container(src):
            stem = sibling_stem(src)
            if stem:
                found.append((stem, None))
        return found

    def plan(self) -> list[Job]:
        jobs: list[Job] = []
        for src in self._iter_tracks():
            siblings = self._siblings(src)
            if not siblings:
                continue
            for dest, suffix in siblings:
                issues = compare_tags(src, dest, title_suffix=suffix)
                if issues:
                    jobs.append(
                        Job(
                            src,
                            dest,
                            "repair" if self.repair else "mismatch",
                            reason="; ".join(issues[:4]),
                            extra={"title_suffix": suffix, "issues": issues},
                        )
                    )
                else:
                    jobs.append(
                        Job(
                            src,
                            dest,
                            "skip",
                            reason="tags match source",
                            extra={"title_suffix": suffix},
                        )
                    )
        return jobs

    def run(self) -> list[Job]:
        jobs = self.plan()
        mismatches = [j for j in jobs if j.action in {"mismatch", "repair"}]
        print(
            f"{'dry-run' if self.dry_run else 'execute'}: "
            f"{len(mismatches)} mismatch / {len(jobs) - len(mismatches)} ok / "
            f"{len(jobs)} sibling files",
            flush=True,
        )
        if self.dry_run or not self.repair:
            for job in mismatches[:40]:
                print(job.describe())
            if len(mismatches) > 40:
                print(f"  … {len(mismatches) - 40} more")
            return self.execute_logged(jobs, None)

        def apply(job: Job) -> dict:
            suffix = job.extra.get("title_suffix")
            written = copy_source_tags(
                job.source,
                job.dest,
                title_suffix=str(suffix) if suffix else None,
            )
            leftover = compare_tags(
                job.source,
                job.dest,
                title_suffix=str(suffix) if suffix else None,
            )
            if leftover:
                raise RuntimeError("; ".join(leftover[:4]))
            return {"handling": "tags_copied", "artist": written.get("artist")}

        return self.execute_logged(jobs, apply)


def qa_after_write(source: Path, dests: list[tuple[Path, str | None]]) -> list[str]:
    """Used by ``py.exec.separate`` after a write. Returns leftover issues."""
    issues: list[str] = []
    for dest, suffix in dests:
        if not dest.is_file():
            continue
        copy_source_tags(source, dest, title_suffix=suffix)
        leftover = compare_tags(source, dest, title_suffix=suffix)
        if leftover:
            issues.extend(f"{dest.name}: {item}" for item in leftover)
    return issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "QA: generated vocals/instrumental/stem files must carry source "
            "artist, label, BPM, cover, title. Dry-run reports; --execute repairs."
        )
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_QUEUE,
        help="M3U, a track, or a folder (default: m3u/nuo_queue_known.m3u)",
    )
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Copy source tags onto mismatched siblings",
    )
    add_log_flags(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tool = MetaValidator(
        args.path,
        dry_run=not args.execute,
        recursive=not args.no_recursive,
        repair=args.execute,
    )
    return run_cli("py.exec.validate_meta", args, tool)


if __name__ == "__main__":
    raise SystemExit(main())
