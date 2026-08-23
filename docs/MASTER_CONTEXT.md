# STEMS — NUO-STEMS + Traktor Pro 4 (`ix`)

## 1. Environment

- **User / Machine**: David / MacBook Pro 16-inch (M5 Max, 64 GB), host `ix`
- **OS**: macOS Tahoe 26.5.1
- **App**: NUO-STEMS 4.0.0 (licensed on this Mac 2026-08-23) — Alex / DJ NUO, [nuo-stems.com](https://nuo-stems.com)
- **Traktor**: Pro 4.5.1 — same Mac. Native link, not export-to-laptop.
- **Library**: 35k+ tracks under `~/Music/stems_audio` — CLI batch is the point; GUI drop does not scale.
- **Python**: 3.12 venv at `.venv/` for the stem factory (`audio-separator`, torch MPS). System 3.9 is too old. `ffmpeg` 9.0.1 + `MP4Box` (gpac) on PATH.
- **GitHub**: https://github.com/ixamal/stems (docs + `py/` — no audio, no NML)
- **Siblings**: [music_migration](https://github.com/ixamal/music_migration) (library / `~/Music/stems_audio`), [blackhole](https://github.com/ixamal/blackhole) (S8 / S88 / BlackHole routing)
- **Older utilities**: [davidrichardnelson/music](https://github.com/davidrichardnelson/music) — source of the OOP ports
- **Journal**: `docs/PROGRESS.md` + `git log`

## 2. What this repo is

A local STEM factory for a **35k+** DJ library: Mel vocals + BS-RoFormer `{name}.stem.m4a` next to the mix, Rekordbox vocals/instrumental when there is voice, extract and catalog. Notes, settings, and `py/` helpers. Not the audio. Not the mixer. Not Apple Music cataloging. This repo is also the public log of ideas we try, keep, or park.

**Inspiration.** [NUO-STEMS](https://nuo-stems.com) (Alex / DJ NUO) is the licensed app on this Mac and the functional reference: algorithm `mel_vocals_bs_others`, sibling NI STEM containers, Rekordbox pair. Those algorithms and functions made this shop possible. NUO has no CLI and rejects `.m3u`; unattended batch over the crate is what this repo adds.

Stems crates stay under `~/Music/stems_audio`. Apple Music stays under `~/Music/Music/Media.localized`. Do not mix those trees.

## 3. NUO-STEMS mode (2026-08-23)

**Legacy / Export**, with **Same as Original** so `{name}.stem.m4a` lands next to the MP3 in `stems_audio`. That matches the crate we already extract for Rekordbox. Native is parked: linked `{hash}.stem.mp4` in `~/Music/Traktor/Stems/`, no M3U drop, tracks must already be in `collection.nml`.

| Mode | Use |
|------|-----|
| Legacy / Export | This Mac. Sibling `.stem.m4a` in `stems_audio`. M3U drop. Default as of 2026-08-23. |
| Traktor Pro 4 Native | Linked stems in Traktor. Parked. Rollback: Settings → Native. |
| DAW / Non-Traktor | Individual WAV/FLAC. Later, if Maschine wants files instead of a STEM container. |

## 4. Paths

| What | Where |
|------|--------|
| Stems tree (DJ crates) | `~/Music/stems_audio/{Artist}/{Album}/` |
| Extracted roles | `{Title} - drums\|bass\|other\|acapella.m4a` in that album folder |
| Rekordbox pair (parallel AAC) | `{stem basename} - vocals.m4a` and `{stem basename} - instrumental.m4a` next to the source. Omitted when vocals have no significant audio (original mix is the instrumental). |
| Playlists | `m3u/*.m3u` — local path lists, not committed. JSON manifests stay in `config/`. |
| Run logs | `log/` — `.log` + JSON + matplotlib charts per CLI run. Verbose default. |
| Apple Music | `~/Music/Music/Media.localized` — **do not write here** |
| Headset MP3s | User-chosen folder (`SIMPLE_MP3`), never stems_audio |
| Traktor collection | `~/Documents/Native Instruments/Traktor 4.5.1/collection.nml` — do not commit; remaps stay in music_migration |
| Rekordbox XML / DB | music_migration — this package does not touch them |
| Quarantine | Gone. David deleted the nameless role WAVs 2026-08-22 after headers proved empty. |
| NUO-STEMS Legacy output | Same as original: `{stem}.stem.m4a` next to the MP3 in `stems_audio`. |
| NUO-STEMS Native output (parked) | `~/Music/Traktor/Stems/{nnn}/{hash}.stem.mp4`. Do not rename. |

## 5. `py/` package

Language folders stay sibling: `py/` now, other languages later. Each tool is a class. Dry-run unless `--execute`.

| Package | Job |
|---------|-----|
| `py.exec` | Stem factory + cleanup. Deps: `py/exec/requirements.txt` |
| `py.utils` | Paths, ffmpeg, catalog, NI stream map, Apple Music guard, run log |
| `py.tools` | Headset MP3, tags, `.trak` |

| Class | Module | Job |
|-------|--------|-----|
| `LocalSeparator` | `py.exec.separate` | Mel pair + BS-RoFormer `.stem.m4a` |
| `StemExtractor` | `py.exec.extract_stems` | NI STEM streams → named M4A |
| `VocalsInstrumental` | `py.exec.vocals_instrumental` | Pair from STEM; else `m3u/nuo_queue.m3u` |
| `UnknownRoleCleanup` | `py.exec.cleanup_unknown` | Nameless role WAVs → quarantine |
| `NumberedDupeCleanup` | `py.exec.cleanup_numbered` | `Name (2).ext` → Trash |
| `AppleFriendly` | `py.utils.apple` | H.264/AAC — never Media.localized |
| `SimpleMp3` | `py.tools.simple_mp3` | 320k MP3 for H2O |
| `TagUpdater` | `py.tools.tag_updater` | Artist / title from filenames |
| `TrakExtractor` | `py.tools.trak_extract` | `.trak` → folder + M3U |
| `RunLogger` | `py.utils.runlog` | `.log` + JSON + overlay charts under `log/` |
| `ProgressPanel` | `py.utils.progress` | Aqua HUD (tkinter, not PyQt) on `--execute` |
| `notify_complete` | `py.utils.notify` | Mail.app to david@alkalurops.org + Mac banner |
| `MetaValidator` | `py.exec.validate_meta` | QA: generated files must carry source tags |

STEM stream map (NI): `1=drums`, `2=bass`, `3=other` (highs / inst), `4=acapella`. Optional `0=master`. See `py.utils.extraction`.

DJ pair (Rekordbox): **vocals** = Mel (or STEM stream 4). **instrumental** = mix minus vocals. Both sit next to the source. If vocals are null, neither pair file is kept — the original mix already is the instrumental. Tracks with no STEM go to `m3u/nuo_queue.m3u` (path list for the CLI; NUO rejects M3U drops).

Rekordbox / Traktor import: add from `stems_audio`. Path remaps stay in [music_migration](https://github.com/ixamal/music_migration).

## 6. Phases

1. Legacy + Same as Original. Prove four tracks from `m3u/nuo_queue_test4.m3u`. **Done 2026-08-23** (Traktor OK).
2. Extract vocals/instrumental next to those new containers. **Done** — mute mixes keep neither pair file.
3. Batch the rest of the crate from `m3u/` (known 446, then full queue, then the 35k+ library). CLI only.
4. Only then talk DAW splits for Maschine sampling.

## 7. Parked / tried

Ideas we are not building yet. Keep them here so a jam does not get lost.

| Idea | Status |
|------|--------|
| **Harvest jam Generate Stems** | Parked 2026-08-23. If David hits Traktor Generate Stems while playing, `{hash}.stem.mp4` lands in `~/Music/Traktor/Stems/`. Later: map AUDIO_ID back to the original, write the Rekordbox pair. Do not rename hash files. |
| **Local Mel-Band-RoFormer CLI** | Four-pack proved 2026-08-23 (MPS, ~55s/track). Rekordbox pair. Empty vocals print `we found none` and delete **vocals and instrumental** (original mix is the instrumental). |
| **Local BS-RoFormer `.stem.m4a`** | Four-pack proved 2026-08-23 in Traktor. ZFTurbo 4-stem + MP4Box. `python3 -m py.exec.separate`. |
| **Library catalog JSON + spreadsheet page** | **TODO later.** Dump the 35k+ crate (and generated siblings) to JSON with all metadata; render a webpage spreadsheet. After the factory is trusted on a 25-track check, then the known queue, then the whole tree. |
