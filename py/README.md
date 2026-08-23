# py/

Python helpers for a **35k+** crate. Language folder is `py/` so later languages can sit beside it. Algorithms and file shapes follow [NUO-STEMS](https://nuo-stems.com) (Alex / DJ NUO); this folder is the CLI because NUO has none.

| Package | What |
|---------|------|
| [`exec/`](exec/) | Stem factory: Mel pair, BS-RoFormer `.stem.m4a`, extract, cleanup. [requirements.txt](exec/requirements.txt) lives here. |
| [`utils/`](utils/) | Paths, ffmpeg, catalog, NI stream map, Apple Music `Media.localized` guard, run log. |
| [`tools/`](tools/) | Headset MP3, filename tags, `.trak` unpack. |

```bash
python3 -m py
.venv/bin/python -m py.exec.separate --path m3u/nuo_queue_test4.m3u
.venv/bin/python -m py.exec.extract_stems --path ~/Music/stems_audio
```

Dry-run unless `--execute`. Verbose `log/` is the default (`--quiet` to skip). `--execute` opens the Aqua progress HUD until Close and mails `david@alkalurops.org`. Never writes `collection.nml`, Rekordbox `master.db`, or Apple Music `Media.localized`.

See [`docs/RUNBOOK.md`](../docs/RUNBOOK.md) and [`docs/settings/py/NOTES.md`](../docs/settings/py/NOTES.md).
