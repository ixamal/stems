# STEMS — NUO-STEMS + Traktor Pro 4 (`ix`)

## 1. Environment

- **User / Machine**: David / MacBook Pro 16-inch (M5 Max, 64 GB), host `ix`
- **OS**: macOS Tahoe 26.5.1
- **App**: NUO-STEMS 4.0.0 (Demo Mode until licensed)
- **Traktor**: Pro 4.5.1 — same Mac. Native link, not export-to-laptop.
- **GitHub**: https://github.com/ixamal/stems (docs only — no audio, no NML)
- **Siblings**: [music_migration](https://github.com/ixamal/music_migration) (library / `~/Music/stems_audio`), [blackhole](https://github.com/ixamal/blackhole) (S8 / S88 / BlackHole routing)
- **Journal**: `docs/PROGRESS.md` + `git log`

## 2. What this repo is

How we generate and attach stems for the Traktor collection. Notes, settings, later maybe helpers. Not the audio. Not the mixer.

## 3. NUO-STEMS mode (2026-08-22)

**Traktor Pro 4 Native.** Creates natively linked STEMS in the Traktor Pro 4 collection. Same idea as Traktor’s Generate Stems.

Do not pick Legacy unless this box is *not* the DJ machine. Do not pick DAW unless we want loose WAV/FLAC for a DAW.

## 4. Paths (from music_migration — confirm next session)

| What | Where |
|------|--------|
| Stems tree (already organized) | `~/Music/stems_audio/{Artist}/{Album}/` |
| Traktor collection | Lives on the machine — do not commit |
| NUO-STEMS output | TBD once Native writes its first track |

## 5. Phases

1. Click Native. Prove one track in Traktor as a STEM.
2. Batch the crate David actually plays.
3. Only then talk DAW splits for Maschine sampling.
