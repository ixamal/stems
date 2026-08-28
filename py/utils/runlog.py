"""py.utils.runlog — verbose run log, per-track JSON, matplotlib charts.

Every CLI writes under ``log/`` by default (``--verbose``, on). ``--quiet``
or ``--no-verbose`` skips files. JSON points at the ``.log`` and records
each source: mutagen tags, vocals/instrumental handling, pass/fail, GPU/CPU/
RSS samples, timestamps. After the batch, charts are drawn from that JSON.
The tracks chart overlays **time per file** (bars) and **elapsed so far**
(line) with source filenames on X. ``--execute`` also opens an Aqua progress
window (``--no-gui`` to skip) and posts a Notification Center banner
(``--no-notify`` to skip).

The neural nets run in child processes (MPS). Parent Torch MPS bytes stay
near zero; we sample the process tree RSS and host CPU/RAM as the practical
allocation picture on Apple Silicon.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
from typing import Any, Callable, Iterator, TextIO

from py.utils.base import Job, Tool
from py.utils.catalog import audio_snapshot
from py.utils.paths import LOG_DIR, ensure_log_dir

NON_WORK_ACTIONS = {"skip", "keep", "queue"}


def _prime_cpu() -> None:
    """First psutil cpu_percent is always 0; warm it once per process."""
    try:
        import psutil

        psutil.cpu_percent(interval=None)
        psutil.Process().cpu_percent(interval=None)
    except Exception:
        pass


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def add_log_flags(parser: argparse.ArgumentParser) -> None:
    """``--verbose`` is the default. ``--quiet`` / ``--no-verbose`` skip files."""
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write .log, JSON, and charts under log/ (default: on)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Same as --no-verbose: do not write log/",
    )
    parser.add_argument(
        "--gui",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Aqua progress window with verbose log (default: on for --execute)",
    )
    parser.add_argument(
        "--notify",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Mail.app to david@alkalurops.org + Mac banner when the batch ends (default: on for --execute)",
    )


def is_verbose(args: argparse.Namespace) -> bool:
    if getattr(args, "quiet", False):
        return False
    return bool(getattr(args, "verbose", True))


def want_gui(args: argparse.Namespace, dry_run: bool) -> bool:
    explicit = getattr(args, "gui", None)
    if explicit is False:
        return False
    if explicit is True:
        return True
    return not dry_run


def want_notify(args: argparse.Namespace, dry_run: bool) -> bool:
    explicit = getattr(args, "notify", None)
    if explicit is False:
        return False
    if explicit is True:
        return True
    return not dry_run


def _fmt_duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, sec = divmod(seconds, 60.0)
    if minutes < 60:
        return f"{int(minutes)}m {sec:.0f}s"
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours}h {minutes}m"


def _host_snapshot() -> dict[str, Any]:
    info: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        "pid": os.getpid(),
    }
    try:
        import psutil

        vm = psutil.virtual_memory()
        info["memory_total_bytes"] = int(vm.total)
        info["memory_available_bytes"] = int(vm.available)
        info["cpu_percent"] = float(psutil.cpu_percent(interval=0.05))
    except Exception:
        pass
    try:
        import torch

        info["torch"] = torch.__version__
        mps = bool(
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        )
        cuda = bool(torch.cuda.is_available())
        info["mps_available"] = mps
        info["cuda_available"] = cuda
        if mps:
            info["gpu_device"] = "mps"
        elif cuda:
            info["gpu_device"] = "cuda"
        else:
            info["gpu_device"] = "cpu"
        if mps:
            info["mps_allocated_bytes"] = int(torch.mps.current_allocated_memory())
            info["mps_driver_bytes"] = int(torch.mps.driver_allocated_memory())
    except Exception:
        info.setdefault("gpu_device", "unknown")
    return info


def _resource_sample() -> dict[str, Any]:
    sample: dict[str, Any] = {"ts": utc_now()}
    try:
        import psutil

        proc = psutil.Process()
        rss = int(proc.memory_info().rss)
        cpu = float(proc.cpu_percent(interval=None))
        for child in proc.children(recursive=True):
            try:
                rss += int(child.memory_info().rss)
                cpu += float(child.cpu_percent(interval=None))
            except (psutil.Error, OSError):
                continue
        vm = psutil.virtual_memory()
        sample["rss_bytes"] = rss
        sample["cpu_percent"] = round(cpu, 2)
        sample["system_memory_used_bytes"] = int(vm.used)
        sample["system_memory_percent"] = float(vm.percent)
        sample["system_cpu_percent"] = float(psutil.cpu_percent(interval=None))
    except Exception:
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            sample["rss_bytes"] = int(usage.ru_maxrss)
        except Exception:
            pass
    try:
        import torch

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            sample["gpu_device"] = "mps"
            sample["gpu_allocated_bytes"] = int(torch.mps.current_allocated_memory())
            sample["gpu_driver_bytes"] = int(torch.mps.driver_allocated_memory())
        elif torch.cuda.is_available():
            sample["gpu_device"] = "cuda"
            sample["gpu_allocated_bytes"] = int(
                torch.cuda.memory_allocated()
            )
        else:
            sample["gpu_device"] = "cpu"
            sample["gpu_allocated_bytes"] = 0
    except Exception:
        sample.setdefault("gpu_device", "unknown")
        sample.setdefault("gpu_allocated_bytes", None)
    return sample


def _summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {"sample_count": 0}
    def _nums(key: str) -> list[float]:
        out = []
        for row in samples:
            val = row.get(key)
            if isinstance(val, (int, float)):
                out.append(float(val))
        return out

    def _peak_mean(key: str) -> dict[str, float | None]:
        vals = _nums(key)
        if not vals:
            return {"peak": None, "mean": None}
        return {"peak": max(vals), "mean": sum(vals) / len(vals)}

    rss = _peak_mean("rss_bytes")
    cpu = _peak_mean("cpu_percent")
    gpu = _peak_mean("gpu_allocated_bytes")
    driver = _peak_mean("gpu_driver_bytes")
    return {
        "sample_count": len(samples),
        "rss_bytes_peak": rss["peak"],
        "rss_bytes_mean": rss["mean"],
        "cpu_percent_peak": cpu["peak"],
        "cpu_percent_mean": cpu["mean"],
        "gpu_allocated_bytes_peak": gpu["peak"],
        "gpu_allocated_bytes_mean": gpu["mean"],
        "gpu_driver_bytes_peak": driver["peak"],
        "gpu_device": samples[-1].get("gpu_device"),
        "samples": samples,
    }


def infer_vocals(job: Job, extra: dict[str, Any] | None = None) -> str:
    if extra and extra.get("vocals") in {"present", "none", "n/a"}:
        return str(extra["vocals"])
    reason = (job.reason or "").lower()
    if extra and extra.get("pair_skip") == "vocal-only":
        return "present"
    if extra and extra.get("pair_skip") == "instrumental-only":
        return "none"
    if job.action == "drop-pair" or "we found none" in reason:
        if "original mix is the vocal" in reason:
            return "present"
        return "none"
    if "no vocals" in reason:
        return "none"
    if "already parallel" in reason or "already complete" in reason:
        return "present"
    return "n/a"


class _Tee:
    def __init__(self, *streams: TextIO, panel: Any = None) -> None:
        self.streams = streams
        self.panel = panel

    def write(self, data: str) -> int:
        for stream in self.streams:
            stream.write(data)
            stream.flush()
        if self.panel is not None:
            try:
                self.panel.write(data)
            except Exception:
                pass
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()

    def isatty(self) -> bool:
        return False


class TrackRecord:
    """One source file across its jobs (pair + container, or four extracts)."""

    def __init__(self, source: Path) -> None:
        self.source = source
        self.started_at = utc_now()
        self.ended_at: str | None = None
        self.wall_s = 0.0
        self.mutagen: dict[str, Any] = {}
        self.jobs: list[dict[str, Any]] = []
        self.result = "skip"
        self.vocals = "n/a"
        self.instrumental = "n/a"
        self.has_audio = True
        self.no_audio = False
        self.handling: list[str] = []
        self.error: str | None = None
        self.resources: dict[str, Any] = {}
        self.audio_duration_s: float | None = None
        self.sec_per_audio_minute: float | None = None
        self._t0 = time.perf_counter()
        self._sampler: _Sampler | None = None

    def start_sampler(self) -> None:
        self._sampler = _Sampler()
        self._sampler.start()

    def stop_sampler(self) -> None:
        if self._sampler is not None:
            self.resources = self._sampler.stop()
            self._sampler = None

    def attach_mutagen(self) -> None:
        self.mutagen = audio_snapshot(self.source)
        length = self.mutagen.get("length_s")
        size = self.mutagen.get("size_bytes")
        self.audio_duration_s = float(length) if length else None
        missing = not self.mutagen.get("exists")
        empty = size == 0
        silent = bool(length == 0)
        self.has_audio = not (missing or empty or silent)
        self.no_audio = not self.has_audio

    def add_job(
        self,
        job: Job,
        *,
        result: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        extra = extra or {}
        vocals = infer_vocals(job, extra)
        instrumental = extra.get("instrumental", "n/a")
        handling = extra.get("handling")
        row = {
            "action": job.action,
            "dest": str(job.dest),
            "role": job.role,
            "reason": job.reason,
            "result": result,
            "vocals": vocals,
            "instrumental": instrumental,
            "handling": handling,
            "error": extra.get("error"),
            "ts": utc_now(),
        }
        self.jobs.append(row)
        if vocals != "n/a":
            self.vocals = vocals
        if instrumental != "n/a":
            self.instrumental = str(instrumental)
        if handling:
            self.handling.append(str(handling))
        if extra.get("has_audio") is False:
            self.has_audio = False
            self.no_audio = True
        if extra.get("error"):
            self.error = str(extra["error"])
        if result == "fail":
            self.result = "fail"
        elif result == "pass" and self.result != "fail":
            self.result = "pass"
        elif result == "planned" and self.result in {"skip"}:
            self.result = "planned"
        elif result == "skip" and self.result == "skip" and not self.jobs[:-1]:
            self.result = "skip"

    def close(self) -> dict[str, Any]:
        self.ended_at = utc_now()
        self.wall_s = round(time.perf_counter() - self._t0, 4)
        if self.audio_duration_s and self.audio_duration_s > 0:
            self.sec_per_audio_minute = round(
                self.wall_s / (self.audio_duration_s / 60.0), 4
            )
        if self.vocals == "none" and self.instrumental == "n/a":
            self.instrumental = "dropped"
        elif self.vocals == "present" and self.instrumental == "n/a":
            self.instrumental = "kept"
        return {
            "source": str(self.source),
            "name": self.source.name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "wall_s": self.wall_s,
            "audio_duration_s": self.audio_duration_s,
            "sec_per_audio_minute": self.sec_per_audio_minute,
            "result": self.result,
            "vocals": self.vocals,
            "instrumental": self.instrumental,
            "has_audio": self.has_audio,
            "no_audio": self.no_audio,
            "handling": self.handling,
            "error": self.error,
            "mutagen": self.mutagen,
            "jobs": self.jobs,
            "resources": {
                k: v
                for k, v in self.resources.items()
                if k != "samples"
            },
            "resource_samples": self.resources.get("samples") or [],
        }


class _Sampler:
    def __init__(self, interval: float = 0.5) -> None:
        self.interval = interval
        self.samples: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.samples.append(_resource_sample())
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self.samples.append(_resource_sample())

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.samples.append(_resource_sample())
        return _summarize_samples(self.samples)


class RunLogger:
    """One automation run: tee to ``.log``, JSON sidecar, charts on close."""

    def __init__(
        self,
        tool_id: str,
        *,
        verbose: bool = True,
        dry_run: bool = True,
        extra: dict[str, Any] | None = None,
        panel: Any = None,
    ) -> None:
        self.tool_id = tool_id
        self.verbose = verbose
        self.dry_run = dry_run
        self.extra = extra or {}
        self.panel = panel
        self.payload: dict[str, Any] | None = None
        self.started_at = utc_now()
        self.ended_at: str | None = None
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        safe = tool_id.replace(" ", "_")
        self.run_id = f"{stamp}-{safe}"
        self.log_path: Path | None = None
        self.json_path: Path | None = None
        self.chart_paths: list[str] = []
        self.tracks: list[dict[str, Any]] = []
        self.host = _host_snapshot()
        _prime_cpu()
        self._log_file: TextIO | None = None
        self._stdout: TextIO | None = None
        self._stderr: TextIO | None = None
        if not verbose and panel is None:
            return
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        if verbose:
            ensure_log_dir()
            self.log_path = LOG_DIR / f"{self.run_id}.log"
            self.json_path = LOG_DIR / f"{self.run_id}.json"
            self._log_file = self.log_path.open("w", encoding="utf-8")
            sys.stdout = _Tee(self._stdout, self._log_file, panel=panel)  # type: ignore[assignment]
            sys.stderr = _Tee(self._stderr, self._log_file, panel=panel)  # type: ignore[assignment]
            print(f"run {self.run_id}  log={self.log_path}", flush=True)
        else:
            sys.stdout = _Tee(self._stdout, panel=panel)  # type: ignore[assignment]
            sys.stderr = _Tee(self._stderr, panel=panel)  # type: ignore[assignment]

    @contextmanager
    def track(self, source: Path) -> Iterator[TrackRecord]:
        rec = TrackRecord(source)
        rec.attach_mutagen()
        if self.verbose:
            rec.start_sampler()
        try:
            yield rec
        finally:
            rec.stop_sampler()
            self.tracks.append(rec.close())

    def close(self) -> Path | None:
        self.ended_at = utc_now()
        payload = self._payload()
        self.payload = payload
        try:
            if self.verbose and self.json_path is not None:
                if self.tracks:
                    try:
                        self.chart_paths = _draw_charts(self.run_id, payload)
                    except Exception as exc:
                        print(f"matplotlib skipped ({exc})", flush=True)
                        self.chart_paths = []
                    payload["charts"] = self.chart_paths
                self.json_path.write_text(json.dumps(payload, indent=2) + "\n")
                print(f"run json: {self.json_path}", flush=True)
                for path in self.chart_paths:
                    print(f"run chart: {path}", flush=True)
        finally:
            if self._stdout is not None:
                sys.stdout = self._stdout
            if self._stderr is not None:
                sys.stderr = self._stderr
            if self._log_file is not None:
                self._log_file.close()
                self._log_file = None
        return self.json_path

    def _payload(self) -> dict[str, Any]:
        results = {"pass": 0, "fail": 0, "skip": 0, "planned": 0}
        vocals = {"present": 0, "none": 0, "n/a": 0}
        no_audio = 0
        walls: list[float] = []
        rates: list[float] = []
        for track in self.tracks:
            results[str(track.get("result") or "skip")] = (
                results.get(str(track.get("result") or "skip"), 0) + 1
            )
            vocals[str(track.get("vocals") or "n/a")] = (
                vocals.get(str(track.get("vocals") or "n/a"), 0) + 1
            )
            if track.get("no_audio"):
                no_audio += 1
            wall = track.get("wall_s")
            if isinstance(wall, (int, float)):
                walls.append(float(wall))
            rate = track.get("sec_per_audio_minute")
            if isinstance(rate, (int, float)):
                rates.append(float(rate))
        elapsed = 0.0
        for track in self.tracks:
            wall = track.get("wall_s")
            elapsed += float(wall) if isinstance(wall, (int, float)) else 0.0
            track["elapsed_s"] = round(elapsed, 4)
        log_rel = None
        if self.log_path is not None:
            log_rel = str(self.log_path.relative_to(LOG_DIR.parent))
        json_rel = None
        if self.json_path is not None:
            json_rel = str(self.json_path.relative_to(LOG_DIR.parent))
        return {
            "run_id": self.run_id,
            "tool": self.tool_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "dry_run": self.dry_run,
            "verbose": self.verbose,
            "log_path": log_rel,
            "json_path": json_rel,
            "charts": self.chart_paths,
            "host": self.host,
            "extra": self.extra,
            "summary": {
                "tracks": len(self.tracks),
                "results": results,
                "vocals": vocals,
                "no_audio": no_audio,
                "wall_s_total": round(sum(walls), 4) if walls else 0,
                "wall_s_mean": (
                    round(sum(walls) / len(walls), 4) if walls else 0
                ),
                "sec_per_audio_minute_mean": (
                    round(sum(rates) / len(rates), 4) if rates else None
                ),
            },
            "tracks": self.tracks,
        }


def execute_logged(
    tool: Tool,
    jobs: list[Job],
    worker: Callable[[Job], dict[str, Any] | None] | None,
) -> list[Job]:
    """Group jobs by source, sample resources, record pass/fail/vocals."""
    logger: RunLogger | None = getattr(tool, "run_log", None)
    panel = getattr(logger, "panel", None) if logger is not None else None
    writes = [job for job in jobs if job.action not in NON_WORK_ACTIONS]
    n_write = len(writes)
    groups = [(source, list(group)) for source, group in groupby(jobs, key=lambda job: job.source)]
    if panel is not None:
        work_n = sum(
            1
            for _, group in groups
            if any(job.action not in NON_WORK_ACTIONS for job in group)
        )
        skip_n = len(groups) - work_n
        panel.set_totals(work_n or len(groups), n_write or len(groups))
        if skip_n:
            print(
                f"skip {skip_n} already complete; HUD follows {work_n} tracks still in play",
                flush=True,
            )
    i = 0
    for source, group in groups:
        if logger is None:
            _run_group(tool, group, worker, writes_index=i, n_write=n_write)
            i += sum(1 for job in group if job.action not in NON_WORK_ACTIONS)
            continue
        with logger.track(source) as rec:
            for job in group:
                if panel is not None and job.action not in NON_WORK_ACTIONS:
                    panel.set_job(
                        i + 1,
                        n_write or 1,
                        source.name,
                        job.action,
                    )
                if tool.dry_run:
                    rec.add_job(
                        job,
                        result="skip" if job.action == "skip" else "planned",
                    )
                    continue
                if job.action in NON_WORK_ACTIONS:
                    rec.add_job(
                        job,
                        result="skip" if job.action == "skip" else "pass",
                    )
                    continue
                i += 1
                if panel is not None:
                    panel.set_job(i, n_write, source.name, job.action)
                try:
                    extra = worker(job) if worker else {}
                    rec.add_job(job, result="pass", extra=extra or {})
                    print(f"ok {i}/{n_write} {job.describe()}", flush=True)
                except Exception as exc:
                    rec.add_job(
                        job,
                        result="fail",
                        extra={"error": str(exc)},
                    )
                    print(f"fail {i}/{n_write} {job.source.name}: {exc}", flush=True)
    return jobs


def _run_group(
    tool: Tool,
    group: list[Job],
    worker: Callable[[Job], dict[str, Any] | None] | None,
    *,
    writes_index: int,
    n_write: int,
) -> None:
    if tool.dry_run or worker is None:
        return
    i = writes_index
    for job in group:
        if job.action in NON_WORK_ACTIONS:
            continue
        i += 1
        try:
            worker(job)
            print(f"ok {i}/{n_write} {job.describe()}", flush=True)
        except Exception as exc:
            print(f"fail {i}/{n_write} {job.source.name}: {exc}", flush=True)


def run_cli(tool_id: str, args: argparse.Namespace, tool: Tool) -> int:
    """Attach a RunLogger, run the tool, write JSON + charts, optional HUD."""
    panel = None
    if want_gui(args, tool.dry_run):
        from py.utils.notify import display_name
        from py.utils.progress import ProgressPanel

        panel = ProgressPanel.try_open(display_name(tool_id))
    logger = RunLogger(
        tool_id,
        verbose=is_verbose(args),
        dry_run=tool.dry_run,
        panel=panel,
    )
    tool.run_log = logger  # type: ignore[attr-defined]

    def work() -> None:
        try:
            tool.run()
        except Exception as exc:
            print(f"run failed: {exc}", flush=True)
        finally:
            try:
                logger.close()
            except Exception as exc:
                print(f"run log close failed: {exc}", flush=True)
            payload = logger.payload or {}
            from py.utils.notify import notify_complete, resolve_charts, summary_from_payload

            summary = summary_from_payload(payload) if payload else f"{tool_id} finished"
            charts = resolve_charts(payload)
            if want_notify(args, tool.dry_run):
                notify_complete(title=tool_id, body=summary, payload=payload)
            if panel is not None:
                try:
                    panel.finish(summary, charts=charts)
                except Exception as exc:
                    print(f"progress GUI finish skipped ({exc})", flush=True)

    if panel is None:
        work()
        return 0
    worker = threading.Thread(target=work, name=f"{tool_id}-run", daemon=False)
    worker.start()
    panel.mainloop()
    worker.join()
    return 0


def _track_labels(tracks: list[dict[str, Any]]) -> list[str]:
    """X-axis: source filenames, truncated so a batch still fits."""
    n = len(tracks)
    max_len = 48 if n <= 6 else 36 if n <= 12 else 22
    labels: list[str] = []
    for i, track in enumerate(tracks):
        name = str(track.get("name") or Path(str(track.get("source") or "")).name or f"track {i + 1}")
        if len(name) > max_len:
            name = name[: max_len - 1] + "…"
        labels.append(_mpl_plain(name))
    return labels


def _mpl_plain(text: str) -> str:
    """Filenames are not math. ``$`` in a title must not enter mathtext."""
    return text.replace("$", "S")


def _chart_ticks(n: int, labels: list[str]) -> tuple[list[int], list[str]]:
    """Sparse ticks on large batches — 1905 filenames will not fit and can crash layout."""
    if n <= 24:
        return list(range(n)), labels
    step = max(1, n // 16)
    ticks = list(range(0, n, step))
    if ticks[-1] != n - 1:
        ticks.append(n - 1)
    return ticks, [str(i + 1) for i in ticks]


def _draw_charts(run_id: str, payload: dict[str, Any]) -> list[str]:
    tracks = payload.get("tracks") or []
    if not tracks:
        return []
    try:
        import matplotlib

        matplotlib.use("Agg")
        if "text.parse_math" in matplotlib.rcParams:
            matplotlib.rcParams["text.parse_math"] = False
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"matplotlib skipped ({exc})", flush=True)
        return []

    try:
        return _draw_charts_body(run_id, payload, tracks, plt)
    except Exception as exc:
        print(f"matplotlib skipped ({exc})", flush=True)
        return []


def _draw_charts_body(
    run_id: str,
    payload: dict[str, Any],
    tracks: list[dict[str, Any]],
    plt: Any,
) -> list[str]:
    ensure_log_dir()
    labels = _track_labels(tracks)
    walls = [float(t.get("wall_s") or 0) for t in tracks]
    elapsed = []
    running = 0.0
    for wall in walls:
        running += wall
        elapsed.append(running)
    rss = [
        (float(t.get("resources", {}).get("rss_bytes_peak") or 0) / (1024 * 1024))
        for t in tracks
    ]
    cpu = [
        float(t.get("resources", {}).get("cpu_percent_peak") or 0) for t in tracks
    ]
    gpu = [
        float(t.get("resources", {}).get("gpu_allocated_bytes_peak") or 0)
        / (1024 * 1024)
        for t in tracks
    ]
    summary = payload.get("summary") or {}
    n = len(tracks)
    ticks, tick_labels = _chart_ticks(n, labels)
    tick_rot = 25 if n <= 6 else 40
    tick_size = 9 if n <= 8 else 7
    x = list(range(n))
    width = max(11.0, min(28.0, 0.55 * min(n, 40) + 8))

    fig, ax = plt.subplots(figsize=(width, 7.2))
    ax.bar(
        x, walls, color="#3b6d9a", alpha=0.88, label="time per file (s)", zorder=2
    )
    ax.set_ylabel("time per file (seconds)")
    ax.set_ylim(bottom=0)
    ax2 = ax.twinx()
    ax2.plot(
        x,
        elapsed,
        color="#c47b3a",
        marker="o" if n <= 48 else None,
        linewidth=2,
        label="elapsed so far (s)",
        zorder=3,
    )
    ax2.set_ylabel("elapsed so far (seconds)")
    ax2.set_ylim(bottom=0)
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        tick_labels, rotation=tick_rot, ha="right", fontsize=tick_size
    )
    ax.set_xlabel("source filename" if n <= 24 else "file index")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left")
    total = float(summary.get("wall_s_total") or (elapsed[-1] if elapsed else 0))
    mean = float(summary.get("wall_s_mean") or (total / n if n else 0))
    rate_mean = summary.get("sec_per_audio_minute_mean")
    rate_note = (
        f"  ·  mean {_fmt_duration(float(rate_mean))} work / audio-min"
        if isinstance(rate_mean, (int, float))
        else ""
    )
    fig.suptitle(_mpl_plain(f"{payload.get('tool')}  {run_id}"), fontsize=11)
    fig.text(
        0.01,
        0.01,
        (
            f"elapsed {_fmt_duration(total)}  ·  mean {_fmt_duration(mean)}/file  "
            f"·  {n} files{rate_note}\n"
            "bars = wall time for that file; line = cumulative elapsed (sequential jobs)"
        ),
        fontsize=8,
        va="bottom",
    )
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    tracks_png = LOG_DIR / f"{run_id}-tracks.png"
    fig.savefig(tracks_png, dpi=120)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(max(12.0, width * 0.9), 8.4))
    ax = axes[0][0]
    ax.bar(x, cpu, color="#5a8f5a")
    ax.set_title("CPU % peak (process tree)")
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        tick_labels, rotation=tick_rot, ha="right", fontsize=tick_size
    )
    ax.set_ylim(bottom=0)
    ax = axes[0][1]
    ax.bar(x, rss, color="#7a5ea8")
    ax.set_title("RSS peak (MB, process tree)")
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        tick_labels, rotation=tick_rot, ha="right", fontsize=tick_size
    )
    ax.set_ylim(bottom=0)
    ax = axes[1][0]
    ax.bar(x, gpu, color="#a85e5e")
    ax.set_title("GPU allocated peak (MB, parent Torch)")
    ax.set_xticks(ticks)
    ax.set_xticklabels(
        tick_labels, rotation=tick_rot, ha="right", fontsize=tick_size
    )
    ax.set_ylim(bottom=0)
    ax = axes[1][1]
    vocals = summary.get("vocals") or {}
    results = summary.get("results") or {}
    cats = [
        "pass",
        "fail",
        "skip",
        "planned",
        "vocals",
        "no vocals",
        "no audio",
    ]
    vals = [
        results.get("pass", 0),
        results.get("fail", 0),
        results.get("skip", 0),
        results.get("planned", 0),
        vocals.get("present", 0),
        vocals.get("none", 0),
        summary.get("no_audio", 0),
    ]
    colors = [
        "#3b6d9a",
        "#a85e5e",
        "#888888",
        "#c47b3a",
        "#5a8f5a",
        "#b0b0b0",
        "#444444",
    ]
    ax.bar(cats, vals, color=colors)
    ax.set_title("pass / fail / vocals vs none")
    ax.tick_params(axis="x", rotation=30)
    fig.suptitle(
        _mpl_plain(
            f"overview  elapsed {_fmt_duration(total)}  ·  "
            f"mean {_fmt_duration(mean)}/file  ·  "
            f"s/audio-min={summary.get('sec_per_audio_minute_mean')}"
        )
    )
    fig.tight_layout()
    overview_png = LOG_DIR / f"{run_id}-overview.png"
    fig.savefig(overview_png, dpi=120)
    plt.close(fig)

    return [
        str(tracks_png.relative_to(LOG_DIR.parent)),
        str(overview_png.relative_to(LOG_DIR.parent)),
    ]
