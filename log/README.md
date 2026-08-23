# log/

Verbose run output from every `py/` CLI. **On by default** (`--verbose`). Pass `--quiet` / `--no-verbose` to skip.

Each automation run writes three kinds of file, same `run_id` stem:

| File | What |
|------|------|
| `{stamp}-{tool}.log` | Full stdout/stderr tee |
| `{stamp}-{tool}.json` | Points at the `.log`. Per-track mutagen tags, vocals / instrumental handling, pass/fail, no-audio, GPU/CPU/RSS samples, timestamps |
| `{stamp}-{tool}-tracks.png` | Bar graph: wall time and seconds of work per minute of audio |
| `{stamp}-{tool}-overview.png` | CPU / RSS / GPU bars plus pass/fail and vocals vs none |

JSON `tracks[].resource_samples` is the matplotlib source. `summary.vocals.none` is mute mixes (Rekordbox pair dropped; original mix is the instrumental). `summary.no_audio` is a source with no duration/bytes.

`.log` / `.json` / `.png` are gitignored (absolute paths on `ix`). Keep this README.

```bash
.venv/bin/python -m py.exec.separate --path m3u/nuo_queue_test4.m3u
```

Example in this folder: `2026-08-23T175409Z-py.exec.separate.*` — four-pack dry-run after Traktor sign-off. Three tracks with vocals, one mute mix (`vocals: none`). Execute runs fill CPU/GPU samples; dry-run is the schema.
