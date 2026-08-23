# py/ tools

Local factory for a **35k+** crate. File shapes and the `mel_vocals_bs_others`
split follow [NUO-STEMS](https://nuo-stems.com) (Alex / DJ NUO); unattended CLI
is this package because NUO has none. Four-pack proved in Traktor 2026-08-23.

Layout (2026-08-23): stem factory in ``py/exec``, shared helpers in ``py/utils``,
other CLIs in ``py/tools``. One requirements file: ``py/exec/requirements.txt``
(root ``requirements.txt`` just includes it).

| Class | Module | Job |
|-------|--------|-----|
| `LocalSeparator` | `py.exec.separate` | Mel pair + BS-RoFormer `.stem.m4a`. Drops empty vocals **and** the instrumental sibling (original mix is the instrumental). |
| `StemExtractor` | `py.exec.extract_stems` | NI STEM → drums / bass / other / acapella |
| `VocalsInstrumental` | `py.exec.vocals_instrumental` | Pair from STEM; else queue into `m3u/` |
| `UnknownRoleCleanup` | `py.exec.cleanup_unknown` | Nameless role WAVs → quarantine |
| `NumberedDupeCleanup` | `py.exec.cleanup_numbered` | Finder `Name (2)` dupes → Trash |
| `AppleFriendly` | `py.utils.apple` | H.264/AAC — `refuse_media_localized` |
| `SimpleMp3` | `py.tools.simple_mp3` | 320k MP3 for the H2O headset |
| `TagUpdater` | `py.tools.tag_updater` | Tags from `Artist - Title` filenames |
| `TrakExtractor` | `py.tools.trak_extract` | `.trak` → folder + M3U |
| `MetaValidator` | `py.exec.validate_meta` | QA source tags on vocals / instrumental / `.stem.m4a` |
| `StemCatalog` | `py.utils.catalog` | Artist/Album dest + skip-if-present |

Shared: `py.utils.base` (`Tool` / `Job`), `py.utils.paths`, `py.utils.ffmpeg`, `py.utils.extraction` (NI stream map), `py.utils.runlog` (verbose `log/` + overlay charts), `py.utils.progress` (Aqua HUD until Close), `py.utils.notify` (Mail.app to david@alkalurops.org), `py.utils.meta` (tag copy). Mux: `py.exec.ni_stem` (MP4Box).

Playlists: `m3u/` (gitignored `.m3u`). JSON manifests stay in `config/`. Run logs: `log/` (artifacts gitignored; README only).

`--verbose` is the default on every CLI: tee to `.log`, per-track JSON (mutagen, vocals/instrumental, pass/fail, no-audio, GPU/CPU/RSS, timestamps), matplotlib overlay (filename X, time-per-file bars + elapsed line). `--quiet` skips files. `--execute` also opens the Aqua progress window (`brew install python-tk@3.12`) until Close, and mails `david@alkalurops.org` via Mail.app. `--no-gui` / `--no-notify` skip. Not PyQt.

## Dedup

Skip when dest exists, or when artist + album + title + role already lives under the catalog root. `--force` overwrites.

## Guardrails

- Default dest for extract: `~/Music/stems_audio`
- `AppleFriendly` / `refuse_media_localized` refuse `~/Music/Music/Media.localized`
- No writes to `collection.nml` or Rekordbox `master.db`
- Nameless `bass|drums|other|vocals (N).wav` go to `stems_audio/_quarantine/` (not Trash)
- Mute-mix vocals: print `we found none`, delete vocals **and** instrumental
- Full set (vocals/acapella + instrumental + `.stem.m4a`): skip unless `--force`
- Generated files get source artist, title, album, label, BPM, key, cover (MP4Box `-itags` on STEM so the NI atom stays). QA: `python3 -m py.exec.validate_meta`
