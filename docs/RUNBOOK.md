# RUNBOOK — NUO Native, then extract

You are on `ix`. Traktor Pro 4.5.1 lives here. You are not rendering for another laptop. Stems crates stay out of Apple Music.

## Welcome: Choose Your NUO-STEMS Mode

1. Leave **Traktor Pro 4 Native** selected (Recommended).
2. Hit **Understand**. Not Show Later — lock the mode.
3. Ignore Legacy / Export. Ignore DAW / Non-Traktor.

That’s the first decision. Native writes a Traktor-linked STEM (M4A-family container). We do not flip NUO to DAW just to get loose files.

## After one Native generate

1. Confirm the track is a STEM in Traktor.
2. Find the `.stem.m4a` / `.stem.mp4` NUO wrote. Log that path in `docs/settings/nuo-stems-4/NOTES.md` the first time.
3. From this repo root:

```bash
python3 -m py
python3 -m py.extract_stems --path /path/to/that/folder
# inspect the plan, then:
python3 -m py.extract_stems --path /path/to/that/folder --execute
```

Default dest is `~/Music/stems_audio/{Artist}/{Album}/{Title} - {role}.m4a` with roles `drums`, `bass`, `other`, `acapella`. Already-present files skip. `--inplace` writes next to the container instead. `--acapella` is vocals only. `--wav` if you really want WAV.

4. In Traktor and Rekordbox, add the new files from `stems_audio`. Do not hand-edit `collection.nml` or `master.db` from this repo. Remaps live in music_migration.

5. Write what happened in `docs/PROGRESS.md`. No audio in git.

## Other tools (any folder)

```bash
python3 -m py.simple_mp3 convert --path ~/some/folder          # dry-run 320k
python3 -m py.simple_mp3 collect --path ~/some/folder --execute
python3 -m py.tag_updater ~/some/folder --execute
python3 -m py.trak_extract ~/some/folder -o ~/Extracted_Sets --execute
python3 -m py.apple_friendly --path ~/some/folder --mode audio
python3 -m py.cleanup_unknown          # nameless bass/drums/other/vocals.wav → _quarantine
python3 -m py.cleanup_unknown --execute
python3 -m py.vocals_instrumental --path ~/Music/stems_audio --extract-only
python3 -m py.vocals_instrumental --path ~/some/stem.stem.m4a --extract-only --execute
python3 -m py.vocals_instrumental --path ~/Music/stems_audio --queue-only --execute
```

Headset MP3s stay in `SIMPLE_MP3` (or `--dest`). Apple-friendly output stays in `ip/` (or `--dest`). Neither writes `Media.localized`.

## Do not

- Commit `.stem.m4a`, WAV, FLAC, NML, `.trak`, or `master.db`.
- Flip NUO to Legacy “just to see.” That’s a second-computer workflow.
- Write extracted stems into Apple Music.
- Open the blackhole repo to debug NUO. Mixer stays over there.
- Run `--execute` on a whole drive without reading the dry-run first.
