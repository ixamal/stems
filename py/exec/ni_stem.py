"""py.exec.ni_stem — mux five AAC files into a Traktor NI STEM container.

ffmpeg multi-stream M4A is not enough: Traktor looks for the ``stem`` udta
atom. MP4Box (gpac) plus base64 JSON is the same recipe Mixxx / stempeg /
Stemgen use.

Stream order (NI): 0 mix, 1 drums, 2 bass, 3 other, 4 vocals.
Requires ``brew install gpac`` so ``MP4Box`` is on PATH.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

class StemMuxError(RuntimeError):
    pass


# NI STEM Creator defaults (drums / bass / other / vocals).
STEM_UDTA = {
    "version": 1,
    "mastering_dsp": {
        "compressor": {
            "enabled": False,
            "input_gain": 6,
            "output_gain": 4.4,
            "threshold": -2.4,
            "dry_wet": 100,
            "attack": 0.001,
            "release": 0.2,
            "ratio": 1.5,
            "hp_cutoff": 50,
        },
        "limiter": {
            "enabled": False,
            "threshold": 0.0,
            "ceiling": -0.35,
            "release": 0.05,
        },
    },
    "stems": [
        {"name": "Drums", "color": "#FD4A4A"},
        {"name": "Bass", "color": "#FFFF00"},
        {"name": "Other", "color": "#00E8E8"},
        {"name": "Vocals", "color": "#AD65FF"},
    ],
}


def mp4box_bin() -> str:
    path = shutil.which("MP4Box")
    if not path:
        raise StemMuxError(
            "MP4Box not on PATH. Install gpac, then retry:\n  brew install gpac"
        )
    return path


def mux_ni_stem(
    dest: Path,
    *,
    master: Path,
    drums: Path,
    bass: Path,
    other: Path,
    vocals: Path,
) -> None:
    """Write ``{name}.stem.m4a``: stream 0 mix, then drums/bass/other/vocals."""
    for role, path in (
        ("master", master),
        ("drums", drums),
        ("bass", bass),
        ("other", other),
        ("vocals", vocals),
    ):
        if not path.is_file() or path.stat().st_size == 0:
            raise StemMuxError(f"missing {role} AAC: {path}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    payload = base64.b64encode(
        json.dumps(STEM_UDTA, separators=(",", ":")).encode()
    ).decode()
    cmd = [
        mp4box_bin(),
        "-add",
        f"{master}#ID=Z",
        str(dest),
        "-add",
        f"{drums}#ID=Z:disable",
        "-add",
        f"{bass}#ID=Z:disable",
        "-add",
        f"{other}#ID=Z:disable",
        "-add",
        f"{vocals}#ID=Z:disable",
        "-brand",
        "M4A:0",
        "-rb",
        "isom",
        "-rb",
        "iso2",
        "-udta",
        f"0:type=stem:src=base64,{payload}",
        "-quiet",
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0 or not dest.exists():
        err = (completed.stderr or completed.stdout or "").strip()
        raise StemMuxError(f"MP4Box failed ({completed.returncode}): {err or dest}")
    if dest.stat().st_size == 0:
        raise StemMuxError(f"MP4Box wrote empty file: {dest}")
