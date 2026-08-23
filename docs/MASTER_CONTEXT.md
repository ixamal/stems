# STEMS — NUO-STEMS + Traktor Pro 4 (`ix`)

## 1. Environment

- **User / Machine**: David / MacBook Pro 16-inch (M5 Max, 64 GB), host `ix`
- **OS**: macOS Tahoe 26.5.1
- **App**: NUO-STEMS 4.0.0 (Demo Mode until licensed)
- **Traktor**: Pro 4.5.1 — same Mac. Native link, not export-to-laptop.
- **Python**: 3.9+ with `mutagen`. System `ffmpeg` (Homebrew 9.0.1 on `ix`).
- **GitHub**: https://github.com/ixamal/stems (docs + `py/` — no audio, no NML)
- **Siblings**: [music_migration](https://github.com/ixamal/music_migration) (library / `~/Music/stems_audio`), [blackhole](https://github.com/ixamal/blackhole) (S8 / S88 / BlackHole routing)
- **Older utilities**: [davidrichardnelson/music](https://github.com/davidrichardnelson/music) — source of the OOP ports
- **Journal**: `docs/PROGRESS.md` + `git log`

## 2. What this repo is

How we generate stems (NUO Native), then extract and catalog the pieces. Notes, settings, and `py/` helpers. Not the audio. Not the mixer. Not Apple Music cataloging.

Stems crates stay under `~/Music/stems_audio`. Apple Music stays under `~/Music/Music/Media.localized`. Do not mix those trees.

## 3. NUO-STEMS mode (2026-08-22)

**Traktor Pro 4 Native.** Creates natively linked STEMS in the Traktor Pro 4 collection. Same idea as Traktor’s Generate Stems. Store / play as M4A-friendly STEM containers, then extract named parts with `py.extract_stems`.

Do not pick Legacy unless this box is *not* the DJ machine. Do not pick DAW unless we want loose WAV/FLAC for a DAW (Maschine, later).

| Mode | Use |
|------|-----|
| Traktor Pro 4 Native | This Mac. Start here. |
| Legacy / Export | Other computer → Traktor Utilities on the DJ laptop. Writes `.stem.m4a`. |
| DAW / Non-Traktor | Individual WAV/FLAC. No `.stem.m4a`. Later. |

## 4. Paths

| What | Where |
|------|--------|
| Stems tree (DJ crates) | `~/Music/stems_audio/{Artist}/{Album}/` |
| Extracted roles | `{Title} - drums\|bass\|other\|acapella.m4a` in that album folder |
| Rekordbox pair (parallel AAC) | `{stem basename} - vocals.m4a` and `{stem basename} - instrumental.m4a` next to the `.stem.m4a`. Container is not modified. |
| Apple Music | `~/Music/Music/Media.localized` — **do not write here** |
| Headset MP3s | User-chosen folder (`SIMPLE_MP3`), never stems_audio |
| Traktor collection | `~/Documents/Native Instruments/Traktor 4.5.1/collection.nml` — do not commit; remaps stay in music_migration |
| Rekordbox XML / DB | music_migration — this package does not touch them |
| Quarantine | Gone. David deleted the nameless role WAVs 2026-08-22 after headers proved empty. |
| NUO-STEMS Native output | Traktor Pro 4 Preferences → Stems folder, as `{hash}.stem.mp4`. Not next to the source. Not the NUO “output folder.” |

## 5. `py/` package

Language folders stay sibling: `py/` now, other languages later. Each tool is a class. Dry-run unless `--execute`. Point `--path` at any folder. Duplicates skip.

| Class | Module | Job |
|-------|--------|-----|
| `StemExtractor` | `py.extract_stems` | NI STEM streams → named M4A under stems_audio |
| `SimpleMp3` | `py.simple_mp3` | 320k MP3 convert / collect for H2O |
| `TagUpdater` | `py.tag_updater` | Artist / title from `Artist - Title` filenames |
| `TrakExtractor` | `py.trak_extract` | `.trak` → folder + M3U |
| `AppleFriendly` | `py.apple_friendly` | H.264/AAC or AAC M4A — never Media.localized |
| `StemCatalog` | `py.catalog` | Artist/Album dest + skip-if-present |
| `VocalsInstrumental` | `py.vocals_instrumental` | Acapella + instrumental from STEM; else NUO queue |
| `UnknownRoleCleanup` | `py.cleanup_unknown` | Nameless `bass (N).wav` pile → quarantine |
| `NumberedDupeCleanup` | `py.cleanup_numbered` | Trash `Name (2).ext` when original exists |

STEM stream map (NI): `1=drums`, `2=bass`, `3=other` (highs / inst), `4=acapella`. Optional `0=master`.

DJ pair (Rekordbox): **vocals** = stream 4 AAC copy. **instrumental** = drums+bass+other mixed to AAC `.m4a`. Both sit next to the untouched `.stem.m4a` (Traktor Native). Tracks with no STEM go to `config/nuo_queue.m3u` for NUO-STEMS 4 (GUI only — Native stays on).

Rekordbox / Traktor import of the new files: add from `stems_audio` after extract. Path remaps and playlist PRIMARYKEYs stay in [music_migration](https://github.com/ixamal/music_migration).

## 6. Phases

1. Click Native. Prove one track in Traktor as a STEM.
2. Extract that container with `py.extract_stems` into stems_audio. Confirm no duplicate write.
3. Batch the crate David actually plays.
4. Only then talk DAW splits for Maschine sampling.
