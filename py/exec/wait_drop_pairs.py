#!/usr/bin/env python3
"""Wait for the running factory PID, then drop leftover Rekordbox pairs.

Does not start Mel or mux stems. Used after the 1905-write batch so we do
not race that process. Dry-run first; ``--execute`` only if drop count is
below the safety cap.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from py.exec.separate import DROP_PAIRS_CAP, LocalSeparator
from py.utils.paths import STEMS_AUDIO

MAX_DROPS = DROP_PAIRS_CAP

# Proved vocal-only leftovers from this batch. Stem must stay; pair must go.
_KNOWN_LEFTOVERS = (
    "Belinda Carlise/Unknown Album/Heaven Is A Place On Earth (Acappella)",
    "Roland Clark/I Get Deep/Roland Clark - I Get Deep (Acapella)",
    "Dan Diamond/Acapellas/John Acquaviva, Olivier Giacomotto, Dan Diamond - Let It Go (Acapella)",
    "Unknown Artist/Unknown Album/Opus III, It's A Fine Day (Acappella Version)",
)


def _verify_known(root: Path) -> int:
    """Return 0 if known leftover pairs are gone and .stem.m4a remains."""
    failed = 0
    for rel in _KNOWN_LEFTOVERS:
        base = root / rel
        stem = Path(str(base) + ".stem.m4a")
        vocals = Path(str(base) + " - vocals.m4a")
        instrumental = Path(str(base) + " - instrumental.m4a")
        stem_ok = stem.is_file() and stem.stat().st_size > 0
        pair_gone = not vocals.exists() and not instrumental.exists()
        status = "ok" if stem_ok and pair_gone else "FAIL"
        print(
            f"verify {status}: {base.name}  stem={int(stem_ok)} "
            f"pair_gone={int(pair_gone)}",
            flush=True,
        )
        if status != "ok":
            failed += 1
    return 1 if failed else 0


def _daemonize(log: Path) -> None:
    """Double-fork so Cursor shell teardown cannot kill the waiter."""
    log.parent.mkdir(parents=True, exist_ok=True)
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    fd = os.open(str(log), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    os.close(fd)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pid",
        type=int,
        default=0,
        help="factory python PID (py.exec.separate), not a parent shell",
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="factory already exited; skip wait and skip the extra dry-run scan",
    )
    parser.add_argument("--path", type=Path, default=STEMS_AUDIO)
    parser.add_argument("--poll", type=int, default=60)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("log/wait-drop-pairs.nohup.out"),
    )
    args = parser.parse_args(argv)
    if args.daemon:
        _daemonize(args.log)
        Path("log/wait-drop-pairs.pid").write_text(str(os.getpid()) + "\n")
        print(f"daemon pid {os.getpid()} waiting for {args.pid or 'now'}", flush=True)
    if not args.now:
        if not args.pid:
            print("--pid required unless --now", flush=True)
            return 2
        pid = args.pid
        print(f"waiting for pid {pid} to exit (poll {args.poll}s)", flush=True)
        while _pid_alive(pid):
            time.sleep(args.poll)
        print(f"pid {pid} gone — drop-pairs-only", flush=True)
        time.sleep(5)
    if not args.execute:
        tool = LocalSeparator(args.path, dry_run=True, drop_pairs_only=True)
        jobs = [j for j in tool.plan() if j.action == "drop-pair"]
        print(f"drop-pair jobs: {len(jobs)} (cap {MAX_DROPS})", flush=True)
        for job in jobs[:30]:
            print(job.describe(), flush=True)
        if len(jobs) > 30:
            print(f"  … {len(jobs) - 30} more", flush=True)
        if not jobs:
            print("nothing to drop", flush=True)
            return 0
        if len(jobs) > MAX_DROPS:
            print(
                f"refusing to execute: {len(jobs)} drops exceeds cap {MAX_DROPS}",
                flush=True,
            )
            return 2
        print("dry-run only; pass --execute after the factory exits", flush=True)
        return 0
    from py.exec.separate import main as separate_main

    # One scan (cap lives in LocalSeparator.run). --no-gui: daemon has no Close.
    rc = separate_main(
        [
            "--path",
            str(args.path),
            "--drop-pairs-only",
            "--execute",
            "--no-gui",
            "--no-notify",
        ]
    )
    print(f"drop-pairs-only execute finished rc={rc}", flush=True)
    verify_rc = _verify_known(Path(args.path).expanduser())
    if verify_rc:
        print("known leftover verify failed", flush=True)
        return verify_rc
    print("known leftover verify ok", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
