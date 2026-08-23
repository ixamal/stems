"""On-screen progress HUD for a running factory job.

Aqua ttk (stdlib tkinter) — not PyQt. Tk must own the main thread; the
factory runs in a worker. Verbose stdout is mirrored into the log pane
(carriage-return tqdm bars redraw in place). The window is screen-wide and
stays until the Close button (enabled when the batch ends). End-of-run
matplotlib PNGs (tracks + overview) appear in the window and attach to mail.

Needs ``brew install python-tk@3.12`` for Homebrew Python. If Tk is missing
or there is no WindowServer, :meth:`ProgressPanel.try_open` returns None
and the CLI stays terminal-only.
"""

from __future__ import annotations

import queue
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from typing import Any


def gui_available() -> bool:
    try:
        import _tkinter  # noqa: F401
    except ImportError:
        return False
    return True


class ProgressPanel:
    """Live window: determinate bar, current file, elapsed, verbose log."""

    def __init__(self, title: str) -> None:
        self._title = title
        self._q: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._t0 = time.perf_counter()
        self._done = False
        self._n_jobs = 1
        self._n_tracks = 1
        self.root = tk.Tk()
        self.root.title(title)
        self.root.update_idletasks()
        screen_w = max(int(self.root.winfo_screenwidth()), 1200)
        screen_h = int(self.root.winfo_screenheight())
        height = max(560, min(int(screen_h * 0.75), screen_h - 40))
        self.root.geometry(f"{screen_w}x{height}+0+0")
        self.root.minsize(900, 400)

        pad = {"padx": 12, "pady": 4}
        self._status = tk.StringVar(value="starting…")
        self._meta = tk.StringVar(value="")
        ttk.Label(self.root, textvariable=self._status, font=("Helvetica", 14)).pack(
            anchor="w", **pad
        )
        ttk.Label(self.root, textvariable=self._meta).pack(anchor="w", **pad)

        self._bar = ttk.Progressbar(
            self.root, mode="determinate", maximum=100, length=720
        )
        self._bar.pack(fill="x", padx=12, pady=8)

        self._log = ScrolledText(
            self.root,
            height=22,
            wrap="none",
            font=("Menlo", 12),
            state="disabled",
        )
        self._log.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self._photos: list[Any] = []
        self._chart_row = ttk.Frame(self.root)

        self._btn_row = ttk.Frame(self.root)
        self._btn_row.pack(fill="x", padx=12, pady=(0, 12))
        self._close_btn = ttk.Button(
            self._btn_row,
            text="Close",
            command=self._close_window,
            state="disabled",
        )
        self._close_btn.pack(side="right")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(200, self._pump)

    @classmethod
    def try_open(cls, title: str) -> ProgressPanel | None:
        if not gui_available():
            print(
                "progress GUI skipped (no Tk). brew install python-tk@3.12",
                flush=True,
            )
            return None
        try:
            return cls(title)
        except Exception as exc:
            print(f"progress GUI skipped ({exc})", flush=True)
            return None

    def set_totals(self, n_tracks: int, n_jobs: int) -> None:
        self._q.put(("totals", (max(1, n_tracks), max(1, n_jobs))))

    def set_job(self, index: int, total: int, name: str, action: str) -> None:
        self._q.put(("job", (index, total, name, action)))

    def write(self, data: str) -> None:
        if data:
            self._q.put(("log", data))

    def finish(self, summary: str, charts: list[Path] | None = None) -> None:
        self._q.put(("finish", (summary, list(charts or []))))

    def mainloop(self) -> None:
        try:
            self.root.mainloop()
        except Exception:
            pass

    def _close_window(self) -> None:
        if not self._done:
            return
        try:
            self.root.destroy()
        except Exception:
            pass

    def _on_close(self) -> None:
        # Stay up until Close is enabled (job finished).
        self._close_window()

    def _pump(self) -> None:
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "totals":
                    self._n_tracks, self._n_jobs = payload
                elif kind == "job":
                    index, total, name, action = payload
                    self._n_jobs = max(total, 1)
                    pct = min(100.0, 100.0 * index / self._n_jobs)
                    self._bar["value"] = pct
                    self._status.set(f"{action}  {index}/{total}  {name}")
                elif kind == "log":
                    self._append(str(payload))
                elif kind == "finish":
                    summary, charts = payload
                    self._done = True
                    self._bar["value"] = 100
                    self._status.set(str(summary))
                    self.root.title(f"{self._title} — done")
                    self._show_charts(charts)
                    try:
                        self._close_btn.configure(state="normal")
                        self.root.deiconify()
                        self.root.lift()
                    except Exception:
                        pass
        except queue.Empty:
            pass
        elapsed = time.perf_counter() - self._t0
        self._meta.set(
            f"elapsed {elapsed / 60:.1f} min   "
            f"{self._n_tracks} tracks   "
            + ("done — charts below, Close when you are finished looking" if self._done else "running — Close enables when the batch ends")
        )
        try:
            self.root.after(80, self._pump)
        except Exception:
            pass

    def _show_charts(self, charts: list[Path]) -> None:
        files = [Path(p) for p in charts if Path(p).is_file()]
        if not files:
            return
        try:
            self._log.pack_configure(expand=False)
            self._chart_row.pack(
                fill="both", expand=True, padx=12, pady=(0, 8), before=self._btn_row
            )
        except Exception:
            return
        self.root.update_idletasks()
        pane_w = max(int(self.root.winfo_width()) - 36, 800)
        pane_h = max(int(self.root.winfo_height() * 0.42), 280)
        cell_w = max(pane_w // max(len(files), 1) - 8, 400)
        cell_h = pane_h
        for path in files:
            photo = self._load_chart(path, cell_w, cell_h)
            if photo is None:
                continue
            self._photos.append(photo)
            cell = ttk.Frame(self._chart_row)
            cell.pack(side="left", fill="both", expand=True, padx=4)
            ttk.Label(cell, text=path.name, font=("Helvetica", 11)).pack(anchor="w")
            ttk.Label(cell, image=photo).pack(fill="both", expand=True)

    def _load_chart(self, path: Path, max_w: int, max_h: int) -> tk.PhotoImage | None:
        try:
            from PIL import Image, ImageTk

            image = Image.open(path)
            image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image, master=self.root)
        except Exception:
            pass
        try:
            photo = tk.PhotoImage(file=str(path), master=self.root)
            factor = max(1, max(photo.width() // max_w, photo.height() // max_h))
            if factor > 1:
                photo = photo.subsample(factor, factor)
            return photo
        except Exception:
            return None

    def _append(self, data: str) -> None:
        """Mirror stdout. Carriage returns (tqdm) redraw the current line."""
        try:
            self._log.configure(state="normal")
            text = data.replace("\r\n", "\n")
            parts = text.split("\r")
            for i, part in enumerate(parts):
                if i:
                    start = self._log.index("end-1c linestart")
                    self._log.delete(start, "end-1c")
                if part:
                    self._log.insert("end", part)
            line_s = self._log.index("end-1c").split(".")[0]
            if line_s.isdigit() and int(line_s) > 4000:
                self._log.delete("1.0", "2000.0")
            self._log.see("end")
            self._log.configure(state="disabled")
        except Exception:
            pass
