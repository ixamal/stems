"""Completion notify: Mail.app plus a local banner.

The mailbox is a local AES blob under ``~/local_tools/secrets/``
(gitignored). This module never stores an address. Mail.app is the
transport. Cursor Cloud Agents are not used for this ping.

A Notification Center banner still fires on this Mac as a fallback.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from py.utils.paths import LOG_DIR, REPO_ROOT

SECRET_BOX = Path.home() / "local_tools" / "secrets" / "box.py"


def notify_to() -> str:
    """Decrypt the local mailbox. Empty if the blob is missing."""
    if not SECRET_BOX.is_file():
        return ""
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("ix_secret_box", SECRET_BOX)
        if spec is None or spec.loader is None:
            return ""
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return str(getattr(mod, "notify_to", lambda: "")() or "").strip()
    except Exception:
        return ""


TOOL_TITLES = {
    "py.exec.separate": "STEMS separation",
    "py.exec.validate_meta": "STEMS metadata QA",
    "py.exec.extract_stems": "STEMS extract",
    "py.exec.vocals_instrumental": "STEMS vocals / instrumental",
    "py.exec.cleanup_unknown": "STEMS cleanup",
    "py.exec.cleanup_numbered": "STEMS numbered cleanup",
}


def display_name(tool_id: str) -> str:
    """Inbox / window title. Separate jobs read as STEMS separation."""
    if tool_id in TOOL_TITLES:
        return TOOL_TITLES[tool_id]
    if "separate" in tool_id:
        return "STEMS separation"
    return f"STEMS {tool_id}"


def _applescript_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _banner(title: str, body: str) -> None:
    script = (
        f"display notification {_applescript_str(body[:200])} "
        f"with title {_applescript_str(title[:80])} "
        'sound name "Glass"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            timeout=8,
        )
    except Exception:
        pass


def resolve_charts(payload: dict[str, Any] | None) -> list[Path]:
    """Absolute PNG paths from a run payload."""
    if not payload:
        return []
    out: list[Path] = []
    for rel in payload.get("charts") or []:
        path = Path(str(rel))
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.is_file():
            path = LOG_DIR / Path(str(rel)).name
        if path.is_file() and path.suffix.lower() == ".png":
            out.append(path.resolve())
    return out


def _mail(subject: str, body: str, attachments: list[Path] | None = None) -> bool:
    """Send via Mail.app, PNG reports attached. Returns True if osascript exited 0."""
    to_addr = notify_to()
    if not to_addr:
        print("mail skipped (no local notify address)", flush=True)
        return False
    attach_lines: list[str] = []
    for path in attachments or []:
        posix = str(path.resolve())
        attach_lines.append(
            "make new attachment with properties "
            f"{{file name:POSIX file {_applescript_str(posix)}}} "
            "at after the last paragraph"
        )
    attach_block = "\n".join(attach_lines)
    script = (
        "tell application \"Mail\"\n"
        f"set msg to make new outgoing message with properties "
        f"{{subject:{_applescript_str(subject[:180])}, "
        f"content:{_applescript_str(body[:3500])}, visible:false}}\n"
        "tell msg\n"
        f"make new to recipient at end of to recipients with properties "
        f"{{address:{_applescript_str(to_addr)}}}\n"
        f"{attach_block}\n"
        "send\n"
        "end tell\n"
        "end tell\n"
    )
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except Exception as exc:
        print(f"mail skipped ({exc})", flush=True)
        return False
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        print(f"mail failed: {err}", flush=True)
        return False
    n = len(attachments or [])
    extra = f" + {n} chart png" if n else ""
    print(f"mail sent{extra}", flush=True)
    return True


def summary_from_payload(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    results = summary.get("results") or {}
    n = int(summary.get("tracks") or 0)
    passed = int(results.get("pass") or 0)
    failed = int(results.get("fail") or 0)
    skipped = int(results.get("skip") or 0)
    wall = float(summary.get("wall_s_total") or 0)
    minutes = wall / 60.0 if wall else 0.0
    tool = display_name(str(payload.get("tool") or "stems"))
    run_id = str(payload.get("run_id") or "")
    if failed:
        return (
            f"{tool} finished with {failed} fail / {passed} pass "
            f"({n} tracks, {minutes:.0f} min). {run_id}"
        )
    return (
        f"{tool} finished: {passed} pass / {skipped} skip "
        f"({n} tracks, {minutes:.0f} min). {run_id}"
    )


def mail_subject(payload: dict[str, Any] | None, title: str, body: str) -> str:
    """Short Gmail subject that still names the job months later."""
    label = display_name(title)
    if payload:
        summary = payload.get("summary") or {}
        results = summary.get("results") or {}
        passed = int(results.get("pass") or 0)
        failed = int(results.get("fail") or 0)
        skipped = int(results.get("skip") or 0)
        wall = float(summary.get("wall_s_total") or 0)
        minutes = wall / 60.0 if wall else 0.0
        if failed:
            return f"{label} — {failed} fail / {passed} pass ({minutes:.0f} min)"
        return f"{label} — {passed} pass / {skipped} skip ({minutes:.0f} min)"
    return f"{label} — {body[:80]}" if body else label


def email_body(payload: dict[str, Any], summary: str) -> str:
    log_path = payload.get("log_path") or ""
    json_path = payload.get("json_path") or ""
    charts = payload.get("charts") or []
    chart_lines = "\n".join(f"  {c}" for c in charts) or "  (none)"
    passed = []
    failed = []
    for track in payload.get("tracks") or []:
        name = str(track.get("name") or "")
        result = str(track.get("result") or "")
        if result == "pass":
            passed.append(name)
        elif result == "fail":
            failed.append(f"{name}: {track.get('error') or 'fail'}")
    pass_block = "\n".join(f"  {n}" for n in passed[:30]) or "  (none)"
    fail_block = "\n".join(f"  {n}" for n in failed[:20]) or "  (none)"
    return (
        f"{summary}\n\n"
        f"host: {payload.get('host', {}).get('hostname', 'ix')}\n"
        f"log: {log_path}\n"
        f"json: {json_path}\n"
        f"charts (also attached as PNG):\n{chart_lines}\n\n"
        f"passed:\n{pass_block}\n\n"
        f"failed:\n{fail_block}\n"
    )


def notify_complete(
    *,
    title: str,
    body: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Banner on this Mac + Mail.app to the local address. Never raises."""
    label = display_name(title)
    _banner(label, body)
    subject = mail_subject(payload, title, body)
    mail_body = email_body(payload, body) if payload else body
    _mail(subject, mail_body, attachments=resolve_charts(payload))
