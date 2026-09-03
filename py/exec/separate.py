#!/usr/bin/env python3
"""py.exec.separate — Rekordbox pair + Traktor ``.stem.m4a``.

NUO-STEMS (Alex / DJ NUO, https://nuo-stems.com) is the licensed reference:
algorithm ``mel_vocals_bs_others``, sibling NI STEM, Rekordbox pair. The app
has no CLI and rejects ``.m3u`` drops. This module is the local factory so a
35k+ crate can run unattended.

**Rekordbox pair** (Kimberley Jensen Mel-Band-RoFormer)::

    {name} - vocals.m4a
    {name} - instrumental.m4a

If either side of the pair has no significant audio, we print
``we found none`` and delete **both** siblings. Mute mix: the source
already is the instrumental. Already-acappella: the source already is
the vocal. ``{name}.stem.m4a`` is still written (drums/bass/other).

**Traktor container** (ZFTurbo 4-stem BS-RoFormer + MP4Box)::

    {name}.stem.m4a   # streams: mix, drums, bass, other, vocals

NUO's recommended algorithm is ``mel_vocals_bs_others``: Mel vocals plus
BS-RoFormer for drums/bass/other. ``bs_roformer`` is that 4-stem checkpoint
in one pass (``model_bs_roformer_ep_17_sdr_9.6568.ckpt``). Mel vocals stay
in the container when they have audio.

Queue lists live in ``m3u/`` (parallel to ``config/``). Dry-run unless
``--execute``. System 3.9 cannot install these models — use the repo
``.venv`` (Homebrew Python 3.12). Needs ``ffmpeg`` and ``MP4Box``
(``brew install gpac``).

See ``py/exec/requirements.txt``. Verbose ``log/`` (``.log``, JSON, matplotlib) is
the default; ``--quiet`` skips files. ``--execute`` opens an Aqua progress
window and a Notification Center banner.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from py.utils.base import Job, Tool
from py.utils.catalog import is_generated_role_file
from py.utils.ffmpeg import (
    audio_duration,
    encode_aac,
    encode_silence_aac,
    is_insignificant_audio,
    is_vocal_only_pair,
)
from py.exec.ni_stem import mux_ni_stem
from py.utils.paths import (
    M3U_DIR,
    SOURCE_TRACK_EXTS,
    STEMS_AUDIO,
    is_stem_container,
    sibling_stem,
    skip_tree,
)
from py.exec.vocals_instrumental import VocalsInstrumental
from py.utils.runlog import add_log_flags, run_cli

KIM_MODEL = "vocals_mel_band_roformer.ckpt"
BS_MODEL = "model_bs_roformer_ep_17_sdr_9.6568.ckpt"
DEFAULT_QUEUE = M3U_DIR / "nuo_queue_test4.m3u"
DROP_PAIRS_CAP = 400


class SeparatorError(RuntimeError):
    pass


def _audio_separator_bin() -> str:
    sibling = Path(sys.executable).resolve().parent / "audio-separator"
    if sibling.is_file():
        return str(sibling)
    path = shutil.which("audio-separator")
    if not path:
        raise SeparatorError(
            "audio-separator not on PATH. Install the ML extra, then retry:\n"
            "  pip install -r py/exec/requirements.txt\n"
            "First run downloads the Kimberley Mel-Band-RoFormer checkpoint."
        )
    return path


class LocalSeparator(Tool):
    """Read an M3U or folder; write AAC pair + NI STEM container."""

    def __init__(
        self,
        source: Path,
        *,
        dry_run: bool = True,
        recursive: bool = True,
        force: bool = False,
        limit: int | None = None,
        model: str = KIM_MODEL,
        bitrate: str = "256k",
        pair: bool = True,
        container: bool = True,
        drop_pairs_only: bool = False,
    ) -> None:
        super().__init__(source, STEMS_AUDIO, dry_run=dry_run, recursive=recursive)
        self.force = force
        self.limit = limit
        self.model = model
        self.bitrate = bitrate
        self.drop_pairs_only = drop_pairs_only
        self.pair = pair and not drop_pairs_only
        self.container = container and not drop_pairs_only
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
        if self.drop_pairs_only:
            return self._iter_pair_mixes()
        found = []
        iterator = src.rglob("*") if self.recursive else src.iterdir()
        for path in iterator:
            if not path.is_file() or path.name.startswith("."):
                continue
            if skip_tree(path) or is_stem_container(path):
                continue
            if path.suffix.lower() not in SOURCE_TRACK_EXTS:
                continue
            if is_generated_role_file(path.name):
                continue
            found.append(path)
        return sorted(found)

    def _mix_path_for_pair(self, pair: Path) -> Path:
        """Source mix next to a Rekordbox pair file, or a dummy path for dest names."""
        name = pair.name
        suffixes = (
            " - vocals.m4a",
            " - instrumental.m4a",
            " - vocals.mp3",
            " - instrumental.mp3",
        )
        base = None
        for suffix in suffixes:
            if name.endswith(suffix):
                base = name[: -len(suffix)]
                break
        if base is None:
            return pair
        for ext in SOURCE_TRACK_EXTS:
            cand = pair.parent / f"{base}{ext}"
            if (
                cand.is_file()
                and not is_stem_container(cand)
                and not is_generated_role_file(cand.name)
            ):
                return cand
        return pair.parent / f"{base}.mp3"

    def _iter_pair_mixes(self) -> list[Path]:
        """Walk existing Rekordbox pairs so leftover acappellas drop even without a mix file.

        Mix titles like ``(Acapella)`` are not generated role siblings. Pair files
        still map back when the mp3 is gone (Roland Clark) or would have been
        skipped by ``role_from_name``.
        """
        root = self.source
        mixes: dict[tuple[str, str], Path] = {}
        globber = root.rglob if self.recursive else root.glob
        for pattern in (
            "* - vocals.m4a",
            "* - instrumental.m4a",
            "* - vocals.mp3",
            "* - instrumental.mp3",
        ):
            for pair in globber(pattern):
                if not pair.is_file() or skip_tree(pair):
                    continue
                mix = self._mix_path_for_pair(pair)
                mixes[(str(mix.parent), mix.stem)] = mix
        return sorted(mixes.values())

    def _vocals_dest(self, src: Path) -> Path:
        existing = self._skipper._pair_already_present(src, "vocals")
        return existing or src.parent / f"{src.stem} - vocals.m4a"

    def _instrumental_dest(self, src: Path) -> Path:
        existing = self._skipper._pair_already_present(src, "instrumental")
        return existing or src.parent / f"{src.stem} - instrumental.m4a"

    def _container_dest(self, src: Path) -> Path:
        return src.parent / f"{src.stem}.stem.m4a"

    def _alive(self, path: Path) -> bool:
        return path.exists() and path.stat().st_size > 0

    def _pair_drop_kind(self, vocals: Path, instrumental: Path) -> str | None:
        """``instrumental-only`` or ``vocal-only`` when the Rekordbox pair is noise.

        ``is_insignificant_audio`` treats a missing path as empty, so we only
        call it on files that exist.
        """
        empty_v = vocals.is_file() and is_insignificant_audio(vocals)
        empty_i = instrumental.is_file() and is_insignificant_audio(instrumental)
        leftover_i = instrumental.is_file() and not vocals.is_file()
        if empty_v or leftover_i:
            return "instrumental-only"
        if empty_i or (
            vocals.is_file()
            and instrumental.is_file()
            and is_vocal_only_pair(vocals, instrumental)
        ):
            return "vocal-only"
        return None

    def _pair_drop_reason(self, kind: str) -> str:
        if kind == "vocal-only":
            return (
                "we found none — skipped vocals and instrumental "
                "(original mix is the vocal)"
            )
        return (
            "we found none — skipped vocals and instrumental "
            "(original mix is the instrumental)"
        )

    def _full_set(self, src: Path) -> tuple[Path, Path, Path] | None:
        """Vocals/acapella + instrumental + stem, all present and usable.

        Mute mixes and already-acappella sources are not a full set (no pair).
        ``--force`` ignores this.
        """
        dest_v = self._vocals_dest(src)
        dest_i = self._instrumental_dest(src)
        dest_c = sibling_stem(src) or self._container_dest(src)
        if not (
            self._alive(dest_v)
            and self._alive(dest_i)
            and self._alive(dest_c)
        ):
            return None
        if self._pair_drop_kind(dest_v, dest_i):
            return None
        return dest_v, dest_i, dest_c

    def _plan_one(self, src: Path) -> list[Job]:
        jobs: list[Job] = []
        dest_v = self._vocals_dest(src)
        dest_i = self._instrumental_dest(src)
        dest_c = sibling_stem(src) or self._container_dest(src)
        full = None if self.force else self._full_set(src)
        if full is not None:
            if self.drop_pairs_only:
                return []
            vocals, instrumental, stem = full
            reason = (
                "already complete "
                f"({vocals.name} + {instrumental.name} + {stem.name})"
            )
            if self.pair:
                jobs.append(
                    Job(
                        source=src,
                        dest=instrumental,
                        action="skip",
                        reason=reason,
                    )
                )
            if self.container:
                jobs.append(
                    Job(
                        source=src,
                        dest=stem,
                        action="skip",
                        reason=reason,
                    )
                )
            return jobs

        drop_kind = None if self.force else self._pair_drop_kind(dest_v, dest_i)
        if drop_kind:
            jobs.append(
                Job(
                    source=src,
                    dest=dest_v if dest_v.exists() else dest_i,
                    action="drop-pair",
                    role="vocals",
                    reason=self._pair_drop_reason(drop_kind),
                    extra={
                        "instrumental": str(dest_i),
                        "vocals": str(dest_v),
                        "pair_skip": drop_kind,
                    },
                )
            )
        if self.drop_pairs_only:
            return jobs
        if self.pair:
            good_pair = dest_v.exists() and dest_i.exists() and drop_kind is None
            cleaned = (
                dest_c.exists()
                and not dest_v.exists()
                and not dest_i.exists()
            )
            if good_pair and not self.force:
                jobs.append(
                    Job(
                        source=src,
                        dest=dest_i,
                        action="skip",
                        reason=f"already parallel ({dest_v.name})",
                    )
                )
            elif drop_kind:
                pass
            elif cleaned and not self.force:
                jobs.append(
                    Job(
                        source=src,
                        dest=dest_c,
                        action="skip",
                        reason="no Rekordbox pair; original mix is enough",
                    )
                )
            else:
                jobs.append(
                    Job(
                        source=src,
                        dest=src.parent / f"{src.stem} - vocals.m4a",
                        action="separate",
                        role="vocals",
                        extra={
                            "instrumental": str(
                                src.parent / f"{src.stem} - instrumental.m4a"
                            ),
                            "model": self.model,
                        },
                    )
                )
        if self.container:
            if dest_c.exists() and dest_c.stat().st_size > 0 and not self.force:
                jobs.append(
                    Job(
                        source=src,
                        dest=dest_c,
                        action="skip",
                        reason="already .stem.m4a",
                    )
                )
            else:
                jobs.append(
                    Job(
                        source=src,
                        dest=self._container_dest(src),
                        action="container",
                        extra={"model": BS_MODEL},
                    )
                )
        return jobs

    def plan(self) -> list[Job]:
        jobs: list[Job] = []
        needed = 0
        tracks = self._iter_tracks()
        n = len(tracks)
        for i, src in enumerate(tracks, 1):
            if self.drop_pairs_only and (i == 1 or i % 50 == 0 or i == n):
                print(f"drop-pairs scan {i}/{n}  {src.name}", flush=True)
            planned = self._plan_one(src)
            writes = [job for job in planned if job.action != "skip"]
            if not writes:
                jobs.extend(planned)
                continue
            if self.limit is not None and needed >= self.limit:
                break
            jobs.extend(planned)
            needed += 1
        return jobs

    def _stamp_tags(
        self,
        source: Path,
        dests: list[tuple[Path, str | None]],
    ) -> None:
        from py.exec.validate_meta import qa_after_write

        for item in qa_after_write(source, dests):
            print(f"tag qa: {item}", flush=True)

    def _run_audio_separator(
        self, source: Path, tmp_path: Path, model: str, names: dict[str, str]
    ) -> None:
        cmd = [
            _audio_separator_bin(),
            str(source),
            "--model_filename",
            model,
            "--output_format",
            "M4A",
            "--output_bitrate",
            self.bitrate,
            "--output_dir",
            str(tmp_path),
            "--custom_output_names",
            json.dumps(names),
        ]
        completed = subprocess.run(cmd, check=False)
        if completed.returncode != 0:
            raise SeparatorError(
                f"audio-separator failed ({completed.returncode}) for {source.name}"
            )

    def _separate_one(self, job: Job) -> Path | None:
        dest_v = job.dest
        dest_i = Path(str(job.extra["instrumental"]))
        with tempfile.TemporaryDirectory(prefix="stems-sep-") as tmp:
            tmp_path = Path(tmp)
            names = {
                "Vocals": dest_v.stem,
                "Instrumental": dest_i.stem,
                "other": dest_i.stem,
                "Other": dest_i.stem,
            }
            self._run_audio_separator(job.source, tmp_path, self.model, names)
            produced_v = tmp_path / dest_v.name
            produced_i = tmp_path / dest_i.name
            if not produced_v.exists() or not produced_i.exists():
                found = sorted(p.name for p in tmp_path.iterdir())
                raise SeparatorError(
                    f"expected {dest_v.name} and {dest_i.name} in temp dir, got {found}"
                )
            dest_v.parent.mkdir(parents=True, exist_ok=True)
            drop_kind = self._pair_drop_kind(produced_v, produced_i)
            if drop_kind:
                produced_v.unlink(missing_ok=True)
                produced_i.unlink(missing_ok=True)
                job.extra["pair_skip"] = drop_kind
                print(
                    f"{self._pair_drop_reason(drop_kind)} for {job.source.name}",
                    flush=True,
                )
                return None
            shutil.move(str(produced_v), str(dest_v))
            shutil.move(str(produced_i), str(dest_i))
            self._stamp_tags(
                job.source,
                [(dest_v, "vocals"), (dest_i, "instrumental")],
            )
            return dest_v

    def _drop_empty_pair(
        self, vocals: Path, instrumental: Path, *, kind: str = "instrumental-only"
    ) -> None:
        """Delete both Rekordbox siblings when one side is silence.

        Instrumental-only: the source mix already *is* the instrumental.
        Vocal-only: the source mix already *is* the vocal. ``.stem.m4a`` stays.
        """
        removed: list[str] = []
        for path in (vocals, instrumental):
            if path.exists():
                path.unlink()
                removed.append(path.name)
        if removed:
            which = (
                "original mix is the vocal"
                if kind == "vocal-only"
                else "original mix is the instrumental"
            )
            print(
                "we found none — deleted "
                + ", ".join(removed)
                + f" ({which})",
                flush=True,
            )

    def _bs_four_stems(self, source: Path, tmp_path: Path) -> dict[str, Path]:
        in_dir = tmp_path / "in"
        out_dir = tmp_path / "wav"
        in_dir.mkdir()
        out_dir.mkdir()
        work = in_dir / source.name
        shutil.copy2(source, work)
        cmd = [
            sys.executable,
            "-m",
            "bs_roformer",
            "--input_folder",
            str(in_dir),
            "--output_folder",
            str(out_dir),
        ]
        completed = subprocess.run(cmd, check=False)
        if completed.returncode != 0:
            raise SeparatorError(
                f"bs_roformer failed ({completed.returncode}) for {source.name}. "
                "Install: pip install -r py/exec/requirements.txt"
            )
        found: dict[str, Path] = {}
        stem = source.stem
        for role in ("drums", "bass", "other", "vocals"):
            candidate = out_dir / f"{stem}_{role}.wav"
            if candidate.exists():
                found[role] = candidate
                continue
            matches = list(out_dir.glob(f"*_{role}.wav"))
            if len(matches) == 1:
                found[role] = matches[0]
        missing = [r for r in ("drums", "bass", "other", "vocals") if r not in found]
        if missing:
            listing = sorted(p.name for p in out_dir.iterdir())
            raise SeparatorError(
                f"bs_roformer missing {missing} for {source.name}, got {listing}"
            )
        return found

    def _container_one(self, job: Job) -> None:
        src = job.source
        dest = job.dest
        with tempfile.TemporaryDirectory(prefix="stems-bs-") as tmp:
            tmp_path = Path(tmp)
            wavs = self._bs_four_stems(src, tmp_path)
            aac_dir = tmp_path / "aac"
            aac_dir.mkdir()
            roles = {}
            for role, wav in wavs.items():
                aac = aac_dir / f"{role}.m4a"
                encode_aac(wav, aac, bitrate=self.bitrate)
                roles[role] = aac
            mel_v = self._vocals_dest(src)
            if (
                mel_v.exists()
                and not is_insignificant_audio(mel_v)
            ):
                roles["vocals"] = mel_v
            elif is_insignificant_audio(roles["vocals"]):
                encode_silence_aac(
                    aac_dir / "vocals-silent.m4a",
                    audio_duration(src) or audio_duration(roles["drums"]),
                )
                roles["vocals"] = aac_dir / "vocals-silent.m4a"
                print(f"we found none — silent vocals in {dest.name}", flush=True)
            master = aac_dir / "master.m4a"
            encode_aac(src, master, bitrate=self.bitrate)
            mux_ni_stem(
                dest,
                master=master,
                drums=roles["drums"],
                bass=roles["bass"],
                other=roles["other"],
                vocals=roles["vocals"],
            )
            self._stamp_tags(src, [(dest, None)])

    def run(self) -> list[Job]:
        jobs = self.plan()
        writes = [j for j in jobs if j.action in {"separate", "container", "drop-pair"}]
        skips = [j for j in jobs if j.action == "skip"]
        if self.drop_pairs_only:
            drops = [j for j in writes if j.action == "drop-pair"]
            print(f"drop-pair jobs: {len(drops)} (cap {DROP_PAIRS_CAP})", flush=True)
            if len(drops) > DROP_PAIRS_CAP:
                raise SeparatorError(
                    f"refusing to drop {len(drops)} pairs (cap {DROP_PAIRS_CAP})"
                )
        mode = "dry-run" if self.dry_run else "execute"
        print(
            f"{mode}: {len(writes)} write / {len(skips)} skip / {len(jobs)} total"
            f"  pair={self.model}  container={BS_MODEL}",
            flush=True,
        )
        if self.dry_run:
            for job in jobs[:40]:
                if job.action == "drop-pair":
                    kind = job.extra.get("pair_skip") or "instrumental-only"
                    print(
                        f"we found none — would delete pair next to "
                        f"{job.source.name} ({kind})"
                    )
                else:
                    print(job.describe())
            if len(jobs) > 40:
                print(f"  … {len(jobs) - 40} more")
            return self.execute_logged(jobs, None)

        def apply(job: Job) -> dict:
            if job.action == "drop-pair":
                kind = str(job.extra.get("pair_skip") or "instrumental-only")
                self._drop_empty_pair(
                    Path(str(job.extra.get("vocals") or job.dest)),
                    Path(str(job.extra["instrumental"])),
                    kind=kind,
                )
                return {
                    "vocals": "present" if kind == "vocal-only" else "none",
                    "instrumental": "dropped",
                    "handling": "dropped_pair",
                    "pair_skip": kind,
                    "has_audio": True,
                }
            if job.action == "separate":
                dest = self._separate_one(job)
                if dest is None:
                    kind = str(job.extra.get("pair_skip") or "instrumental-only")
                    return {
                        "vocals": "present" if kind == "vocal-only" else "none",
                        "instrumental": "dropped",
                        "handling": "dropped_pair",
                        "pair_skip": kind,
                        "has_audio": True,
                    }
                return {
                    "vocals": "present",
                    "instrumental": "kept",
                    "handling": "wrote_pair",
                    "has_audio": True,
                }
            if job.action == "container":
                self._container_one(job)
                return {"handling": "wrote_container"}
            raise SeparatorError(f"unknown action {job.action}")

        return self.execute_logged(jobs, apply)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mel-Band-RoFormer vocals/instrumental plus BS-RoFormer .stem.m4a. "
            "Writes next to the source. Dry-run by default."
        )
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_QUEUE,
        help="M3U, a single audio file, or a folder (default: m3u/nuo_queue_test4.m3u)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Redo even when vocals/acapella + instrumental + .stem.m4a already exist",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max tracks that still need work (complete sets do not count)",
    )
    parser.add_argument("--model", default=KIM_MODEL)
    parser.add_argument("--bitrate", default="256k")
    parser.add_argument("--no-recursive", action="store_true")
    parser.add_argument(
        "--pair-only",
        action="store_true",
        help="Rekordbox vocals/instrumental only (no .stem.m4a)",
    )
    parser.add_argument(
        "--container-only",
        action="store_true",
        help="Traktor .stem.m4a only (skip the Rekordbox pair)",
    )
    parser.add_argument(
        "--drop-pairs-only",
        action="store_true",
        help=(
            "Delete Rekordbox pair files when vocals or instrumental is "
            "silence. Does not run Mel or mux .stem.m4a (post-batch cleanup)."
        ),
    )
    parser.add_argument("--execute", action="store_true")
    add_log_flags(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tool = LocalSeparator(
        args.path,
        dry_run=not args.execute,
        recursive=not args.no_recursive,
        force=args.force,
        limit=args.limit,
        model=args.model,
        bitrate=args.bitrate,
        pair=not args.container_only,
        container=not args.pair_only,
        drop_pairs_only=args.drop_pairs_only,
    )
    return run_cli("py.exec.separate", args, tool)


if __name__ == "__main__":
    raise SystemExit(main())
