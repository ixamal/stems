# py/ tools

Ported from [davidrichardnelson/music](https://github.com/davidrichardnelson/music) into classes. Run from repo root. `ffmpeg` + `mutagen` required.

| Class | Module | Source script |
|-------|--------|----------------|
| `StemExtractor` | `extract_stems.py` | `extract_stems.py` |
| `SimpleMp3` | `simple_mp3.py` | `simple_mp3.py` + `simple_mp3_folder.py` |
| `TagUpdater` | `tag_updater.py` | `tag_updater.py` |
| `TrakExtractor` | `trak_extract.py` | `trak_extract.py` |
| `AppleFriendly` | `apple_friendly.py` | `convert_to_apple_friendly.py` |
| `UnknownRoleCleanup` | `cleanup_unknown.py` | new — quarantine nameless role WAVs |
| `NumberedDupeCleanup` | `cleanup_numbered.py` | new — trash `Name (2).ext` if original same size |
| `VocalsInstrumental` | `vocals_instrumental.py` | new — acapella copy + instrumental mix; NUO queue |

Shared: `StemCatalog` (dest + skip), `Tool` / `Job` (dry-run plan), `paths.sanitize` (same rules as music_migration organize).

## Dedup

Skip when dest exists, or when artist + album + title + role already lives under the catalog root. `--force` overwrites.

## Guardrails

- Default dest for extract: `~/Music/stems_audio`
- `AppleFriendly` refuses `~/Music/Music/Media.localized`
- No writes to `collection.nml` or Rekordbox `master.db`
- Nameless `bass|drums|other|vocals (N).wav` go to `stems_audio/_quarantine/` (not Trash)
