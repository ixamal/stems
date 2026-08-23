# stems

David’s NUO-STEMS shop on `ix`. [ixamal](https://github.com/ixamal) / [alkalurops.org](https://www.alkalurops.org).

Grab tracks → NUO-STEMS 4 (**Traktor Pro 4 Native**) → extract named parts → catalog under `~/Music/stems_audio`. Same machine as Traktor. Audio stays on disk. Apple Music stays in its own tree.

**First click (that welcome screen):** **Traktor Pro 4 Native**. Hit Understand. That’s the one NI’s Generate Stems button would have made. You are not on a second PC.

| Mode | When |
|------|------|
| **Traktor Pro 4 Native** | This Mac. Links stems into the Traktor 4 collection. Start here. |
| Legacy / Export | Only if you render on a *different* computer, then Traktor Utilities on the DJ laptop. |
| DAW / Non-Traktor | WAV/FLAC splits. Later, if Maschine wants files instead of a Traktor STEM. |

Demo Mode is fine to prove one track. License when the pipe is real.

## `py/` tools

OOP ports of [davidrichardnelson/music](https://github.com/davidrichardnelson/music). From the repo root (`ffmpeg` + `pip install -r requirements.txt`):

```bash
python3 -m py
python3 -m py.extract_stems --path ~/path/to/stem-containers
python3 -m py.extract_stems --path ~/path/to/stem-containers --execute
```

Dry-run is the default. Extract writes `{Title} - drums|bass|other|acapella.m4a` under `~/Music/stems_audio/{Artist}/{Album}/` and skips files already there.

| Module | Class | What |
|--------|-------|------|
| `py.extract_stems` | `StemExtractor` | NI STEM → named M4As in stems_audio |
| `py.simple_mp3` | `SimpleMp3` | 320k MP3 for the H2O headset |
| `py.tag_updater` | `TagUpdater` | Tags from `Artist - Title` filenames |
| `py.trak_extract` | `TrakExtractor` | `.trak` → folder + M3U |
| `py.apple_friendly` | `AppleFriendly` | Apple-friendly video/audio — not Music.app |
| `py.vocals_instrumental` | `VocalsInstrumental` | Vocals + instrumental AAC next to STEM; else NUO queue |
| `py.cleanup_unknown` | `UnknownRoleCleanup` | Nameless role WAVs → quarantine |
| `py.cleanup_numbered` | `NumberedDupeCleanup` | Finder `Name (2)` dupes → Trash |

Library remaps stay in [ixamal/music_migration](https://github.com/ixamal/music_migration). The mixer cable is [ixamal/blackhole](https://github.com/ixamal/blackhole).

License: [Apache-2.0](LICENSE).

## Docs

| Doc | What |
|-----|------|
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Native click, then extract |
| [`docs/MASTER_CONTEXT.md`](docs/MASTER_CONTEXT.md) | Paths, package map, what this repo is not |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | The log |
| [`docs/settings/nuo-stems-4/NOTES.md`](docs/settings/nuo-stems-4/NOTES.md) | NUO app notes |
| [`docs/settings/py/NOTES.md`](docs/settings/py/NOTES.md) | Tool / class map |

GitHub is docs + `py/`. No stems audio, no NML, no collection dumps.
