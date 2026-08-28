#!/usr/bin/env python3
"""Prove Mel pair drop kind: mute vs acappella vs both-live. No GPU, no crate."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from py.exec.separate import LocalSeparator
from py.utils.ffmpeg import encode_silence_aac, run_ffmpeg


def _tone(dest: Path, seconds: float = 2.0, *, volume_db: float | None = None) -> None:
    af = []
    if volume_db is not None:
        af.extend(["-af", f"volume={volume_db}dB"])
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            *af,
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            str(dest),
        ]
    )


def main() -> int:
    with TemporaryDirectory(prefix="stems-pair-drop-") as tmp:
        root = Path(tmp)
        sep = LocalSeparator(root, dry_run=True, drop_pairs_only=True)
        silent = root / "silent.m4a"
        loud = root / "loud.m4a"
        encode_silence_aac(silent, 2.0)
        _tone(loud)
        assert sep._pair_drop_kind(silent, loud) == "instrumental-only"
        assert sep._pair_drop_kind(loud, silent) == "vocal-only"
        assert sep._pair_drop_kind(loud, loud) is None
        assert sep._pair_drop_kind(silent, silent) == "instrumental-only"
        bleed = root / "bleed.m4a"
        _tone(bleed, volume_db=-47.0)
        assert sep._pair_drop_kind(loud, bleed) == "vocal-only"
        mix = root / "Track.m4a"
        _tone(mix)
        (root / "Track - vocals.m4a").write_bytes(loud.read_bytes())
        (root / "Track - instrumental.m4a").write_bytes(silent.read_bytes())
        (root / "Track.stem.m4a").write_bytes(b"not-a-real-stem")
        jobs = sep._plan_one(mix)
        actions = [job.action for job in jobs]
        kinds = [job.extra.get("pair_skip") for job in jobs]
        assert actions == ["drop-pair"], actions
        assert kinds == ["vocal-only"], kinds
        assert not any(job.action in {"separate", "container"} for job in jobs)

        from py.utils.catalog import is_generated_role_file, role_from_name

        assert is_generated_role_file("Track - vocals.m4a")
        assert not is_generated_role_file("Song (Acapella).mp3")
        assert role_from_name("Song (Acapella).mp3") == "vocals"

        titled = root / "Song (Acapella).m4a"
        _tone(titled)
        (root / "Song (Acapella) - vocals.m4a").write_bytes(loud.read_bytes())
        (root / "Song (Acapella) - instrumental.m4a").write_bytes(silent.read_bytes())
        (root / "Song (Acapella).stem.m4a").write_bytes(b"not-a-real-stem")
        titled_jobs = sep._plan_one(titled)
        assert [j.action for j in titled_jobs] == ["drop-pair"]
        assert titled_jobs[0].extra.get("pair_skip") == "vocal-only"

        (root / "Orphan (Acapella) - vocals.m4a").write_bytes(loud.read_bytes())
        (root / "Orphan (Acapella) - instrumental.m4a").write_bytes(silent.read_bytes())
        (root / "Orphan (Acapella).stem.m4a").write_bytes(b"not-a-real-stem")
        mixes = {p.stem for p in sep._iter_tracks()}
        assert "Song (Acapella)" in mixes
        assert "Orphan (Acapella)" in mixes
        orphan = root / "Orphan (Acapella).mp3"
        orphan_jobs = sep._plan_one(orphan)
        assert [j.action for j in orphan_jobs] == ["drop-pair"]
        assert orphan_jobs[0].extra.get("pair_skip") == "vocal-only"
    print("ok pair-drop: instrumental-only / vocal-only / both-live / plan / acapella-title / orphan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
