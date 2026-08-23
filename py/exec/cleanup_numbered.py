#!/usr/bin/env python3
"""py.exec.cleanup_numbered — trash ``Name (2).ext`` Finder clones.

Keeps ``01 Final Impact.stem.m4a``. Trashes ``01 Final Impact (2).stem.m4a``
if sizes match (default tolerance 0.05). Does not touch Rekordbox pair files.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from py.utils.base import Job, Tool
from py.utils.paths import CONFIG_DIR, STEMS_AUDIO, STEM_CONTAINERS, ensure_config_dir, skip_tree
from py.utils.runlog import add_log_flags, run_cli

NUMBERED = re.compile(r"^(.+) \((\d+)\)$")


def original_for(path: Path) -> Path | None:
    name = path.name
    suffixes = list(STEM_CONTAINERS) + [path.suffix.lower()]
    seen: set[str] = set()
    for suffix in suffixes:
        if not suffix or suffix in seen:
            continue
        seen.add(suffix)
        if not name.lower().endswith(suffix):
            continue
        stem = name[: -len(suffix)]
        match = NUMBERED.match(stem)
        if match:
            return path.with_name(f"{match.group(1)}{name[len(stem):]}")
    return None


def trash(path: Path) -> None:
    """Move into ~/.Trash so David can undo. Avoids AppleScript quoting bugs."""
    trash_dir = Path.home() / ".Trash"
    trash_dir.mkdir(exist_ok=True)
    dest = trash_dir / path.name
    n = 1
    while dest.exists():
        dest = trash_dir / f"{path.stem} {n}{path.suffix}"
        n += 1
        if n > 10_000:
            raise RuntimeError(f"Trash name collision for {path.name}")
    try:
        path.rename(dest)
    except OSError:
        shutil.move(str(path), str(dest))


def size_ratio(dupe_size: int, original_size: int) -> float:
    """|dupe - original| / original. 0.005 = half a percent."""
    if original_size <= 0:
        return 1.0
    return abs(dupe_size - original_size) / original_size


class NumberedDupeCleanup(Tool):
    """Trash numbered copies within a relative size tolerance of the original."""

    def __init__(
        self,
        source: Path | None = None,
        *,
        dry_run: bool = True,
        recursive: bool = True,
        tolerance: float = 0.05,
    ) -> None:
        super().__init__(
            source or STEMS_AUDIO,
            None,
            dry_run=dry_run,
            recursive=recursive,
        )
        if tolerance < 0:
            raise ValueError("tolerance must be >= 0")
        self.tolerance = tolerance

    def _candidates(self) -> list[tuple[Path, Path, int, int, float]]:
        found: list[tuple[Path, Path, int, int, float]] = []
        if self.source.is_file():
            paths = [self.source]
        elif self.source.is_dir():
            iterator = self.source.rglob("*") if self.recursive else self.source.iterdir()
            paths = [
                p
                for p in iterator
                if p.is_file() and not p.name.startswith(".") and not skip_tree(p)
            ]
        else:
            return []
        for path in sorted(paths):
            original = original_for(path)
            if original is None or not original.exists():
                continue
            if original.resolve() == path.resolve():
                continue
            try:
                dupe_size = path.stat().st_size
                orig_size = original.stat().st_size
            except OSError:
                continue
            if dupe_size <= 0 or orig_size <= 0:
                continue
            ratio = size_ratio(dupe_size, orig_size)
            found.append((path, original, dupe_size, orig_size, ratio))
        return found

    def plan(self) -> list[Job]:
        jobs = []
        for dupe, original, dupe_size, orig_size, ratio in self._candidates():
            if ratio <= self.tolerance:
                action = "trash"
                reason = (
                    f"within {self.tolerance:.4f} of {original.name} "
                    f"(ratio {ratio:.6f}; {dupe_size} vs {orig_size})"
                )
            else:
                action = "keep"
                reason = (
                    f"out of tolerance {self.tolerance:.4f}: ratio {ratio:.6f} "
                    f"({dupe_size} vs {orig_size} {original.name})"
                )
            jobs.append(Job(source=dupe, dest=original, action=action, reason=reason))
        return jobs

    def run(self) -> list[Job]:
        jobs = self.plan()
        trash_jobs = [j for j in jobs if j.action == "trash"]
        keep_jobs = [j for j in jobs if j.action == "keep"]
        mode = "dry-run" if self.dry_run else "execute"
        print(
            f"{mode}: tolerance {self.tolerance:.4f} → "
            f"{len(trash_jobs)} trash / {len(keep_jobs)} out-of-tolerance"
        )
        if trash_jobs:
            print("\nTRASH (within tolerance)")
            for job in trash_jobs:
                print(job.describe())
        if keep_jobs:
            print("\nKEEP (out of tolerance)")
            for job in keep_jobs:
                print(job.describe())
        if not jobs:
            print("Nothing to do.")
        if self.dry_run:
            return self.execute_logged(jobs, None)
        def apply(job: Job) -> dict:
            trash(job.source)
            return {"handling": "trash"}

        jobs = self.execute_logged(jobs, apply)
        ensure_config_dir()
        manifest = CONFIG_DIR / "numbered_dupe_cleanup.json"
        payload = {
            "written_at": datetime.now(timezone.utc).isoformat(),
            "tolerance": self.tolerance,
            "trashed": [
                {"path": str(j.source), "kept": str(j.dest), "reason": j.reason}
                for j in trash_jobs
            ],
            "out_of_tolerance": [
                {"path": str(j.source), "original": str(j.dest), "reason": j.reason}
                for j in keep_jobs
            ],
        }
        manifest.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"manifest: {manifest}")
        return jobs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Trash Name (2).ext when Name.ext exists and sizes are within "
            "--tolerance (relative). Dry-run by default."
        )
    )
    parser.add_argument("--path", type=Path, default=STEMS_AUDIO)
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="Max |dupe-original|/original (default 0.05)",
    )
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument("--execute", action="store_true")
    add_log_flags(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tool = NumberedDupeCleanup(
        args.path,
        dry_run=not args.execute,
        recursive=not args.no_recursive,
        tolerance=args.tolerance,
    )
    return run_cli("py.exec.cleanup_numbered", args, tool)


if __name__ == "__main__":
    raise SystemExit(main())
