#!/usr/bin/env python3
"""py.exec.cleanup_unknown — quarantine nameless bass/drums/other/vocals WAVs.

These are untagged splits (``bass (159).wav``) sitting in Unknown Artist /
Unknown Album. Real tracks that merely start with Bass- (Bassnectar) stay.
Moves to ``stems_audio/_quarantine/`` so Traktor links can be restored.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from py.utils.base import Job, Tool
from py.utils.paths import CONFIG_DIR, STEMS_AUDIO, ensure_config_dir
from py.utils.runlog import add_log_flags, run_cli

ROLE_WAV = re.compile(r"^(bass|drums|other|vocals)( \(\d+\))?\.wav$", re.I)
DEFAULT_SOURCE = STEMS_AUDIO / "Unknown Artist" / "Unknown Album"


class UnknownRoleCleanup(Tool):
    """Move nameless role WAVs out of a folder. Dry-run unless execute."""

    def __init__(
        self,
        source: Path | None = None,
        dest: Path | None = None,
        *,
        dry_run: bool = True,
        stamp: str | None = None,
    ) -> None:
        src = Path(source).expanduser() if source else DEFAULT_SOURCE
        day = stamp or datetime.now().strftime("%Y-%m-%d")
        quarantine = dest or (STEMS_AUDIO / "_quarantine" / f"{day}-unknown-role-wavs")
        super().__init__(src, quarantine, dry_run=dry_run, recursive=False)

    def discover(self) -> list[Path]:
        if not self.source.is_dir():
            return []
        return sorted(
            path
            for path in self.source.iterdir()
            if path.is_file() and ROLE_WAV.match(path.name)
        )

    def plan(self) -> list[Job]:
        assert self.dest is not None
        jobs: list[Job] = []
        for src in self.discover():
            dest = self.dest / src.name
            if dest.exists():
                jobs.append(Job(src, dest, "skip", "already in quarantine"))
            else:
                jobs.append(Job(src, dest, "quarantine"))
        return jobs

    def run(self) -> list[Job]:
        jobs = self.plan()
        self.print_plan(jobs)

        def apply(job: Job) -> dict:
            assert self.dest is not None
            self.dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(job.source), str(job.dest))
            return {"handling": "quarantine"}

        jobs = self.execute_logged(jobs, None if self.dry_run else apply)
        if self.dry_run:
            return jobs
        ensure_config_dir()
        manifest = CONFIG_DIR / "unknown_role_quarantine.json"
        payload = {
            "written_at": datetime.now(timezone.utc).isoformat(),
            "source": str(self.source),
            "dest": str(self.dest),
            "jobs": [
                {"action": job.action, "source": str(job.source), "dest": str(job.dest)}
                for job in jobs
            ],
        }
        manifest.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"manifest: {manifest}")
        print(f"rollback: mv {self.dest!s}/* {self.source!s}/")
        return jobs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Quarantine bass/drums/other/vocals.wav clones in Unknown Album. "
            "Dry-run by default. Does not delete."
        )
    )
    parser.add_argument("--path", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    add_log_flags(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tool = UnknownRoleCleanup(args.path, args.dest, dry_run=not args.execute)
    return run_cli("py.exec.cleanup_unknown", args, tool)


if __name__ == "__main__":
    raise SystemExit(main())
