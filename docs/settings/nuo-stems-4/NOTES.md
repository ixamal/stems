# NUO-STEMS 4

Version seen: **4.0.0**. Badge: **Demo Mode**. License transfer emailed 2026-08-22 — wait for activation before a big queue.

## Mode

**Traktor Pro 4 Native** — selected on first launch, 2026-08-22.

Creates natively linked STEMS in the Traktor Pro 4 collection. Same job as Traktor’s Generate Stems button.

| Mode | Use |
|------|-----|
| Traktor Pro 4 Native | This Mac. Start here. |
| Legacy / Export | Other computer → Traktor Utilities on the DJ laptop. |
| DAW / Non-Traktor | Individual WAV/FLAC or instrumental+acapella. No `.stem.m4a`. Later. |

Sidebar we have not opened yet: Home, Traktor Pro 4, Traktor Utilities, Settings, Documentation.

## Where Native writes

Official FAQ (2026-08-22): Native saves `{hash}.stem.mp4` **only** in the folder set under Traktor Pro 4 Preferences → Stems. Example: `.../Traktor/Stems/069/F0ILIYDQZQLICDIKTDVCBPX0XLPC.stem.mp4`. It does **not** write next to the source MP3, and it does **not** use the NUO-STEMS “output folder.”

`.stem.m4a` next to the original (how `stems_audio` already looks) is **Legacy / Export**. Do not flip Native without a documented rollback.

## Still unknown

- Exact Stems folder path on this Mac (Traktor Preferences)
- How it finds `collection.nml`
- Demo limits (count / watermark / export)

After the first generate, extract with `python3 -m py.extract_stems --path <that folder>` (dry-run first). Native stays selected; we do not switch NUO to DAW just to get loose files.

NUO-STEMS 4.app has **no CLI**. Tracks that need a STEM are listed in `config/nuo_queue.m3u` by `py.vocals_instrumental --queue-only`. Drag that playlist into the app.

Log answers here after the first generate.
