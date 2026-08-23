"""py.utils.base — job record and dry-run / execute switch.

Every CLI tool subclasses :class:`Tool`. ``dry_run`` is the default; pass
``--execute`` to write. :class:`Job` is the plan row printed to stdout.

:class:`Tool.run_log` is attached by ``py.utils.runlog.run_cli`` so every
batch writes ``log/*.log``, JSON, and matplotlib charts (verbose default).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class Job:
    source: Path
    dest: Path
    action: str
    reason: str = ""
    role: str | None = None
    stream_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        role = f" [{self.role}]" if self.role else ""
        why = f" — {self.reason}" if self.reason else ""
        return f"{self.action:8} {self.source.name}{role} -> {self.dest}{why}"


class Tool:
    """Base for each CLI tool. Dry-run is the default."""

    run_log: Any = None

    def __init__(
        self,
        source: Path,
        dest: Path | None = None,
        *,
        dry_run: bool = True,
        recursive: bool = True,
    ) -> None:
        self.source = Path(source).expanduser().resolve()
        self.dest = Path(dest).expanduser().resolve() if dest else None
        self.dry_run = dry_run
        self.recursive = recursive
        self.run_log = None

    def plan(self) -> list[Job]:
        raise NotImplementedError

    def run(self) -> list[Job]:
        raise NotImplementedError

    def execute_logged(
        self,
        jobs: list[Job],
        worker: Callable[[Job], dict[str, Any] | None] | None = None,
    ) -> list[Job]:
        from py.utils.runlog import execute_logged

        return execute_logged(self, jobs, worker)

    def print_plan(self, jobs: list[Job]) -> None:
        if not jobs:
            print("Nothing to do.")
            return
        skips = sum(1 for job in jobs if job.action == "skip")
        writes = len(jobs) - skips
        mode = "dry-run" if self.dry_run else "execute"
        print(f"{mode}: {writes} write / {skips} skip / {len(jobs)} total")
        for job in jobs:
            print(job.describe())
