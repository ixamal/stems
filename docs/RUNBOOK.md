# RUNBOOK — local STEM factory, then extract

You are on `ix`. Traktor Pro 4.5.1 lives here. Stems crates stay out of Apple Music. The crate is **35k+**; the generator is the CLI, not a GUI drop.

## Mode (NUO, parked)

Local CLI is the generator (`py.exec.separate`). [NUO-STEMS](https://nuo-stems.com) (Alex / DJ NUO) stays licensed for comparison — we match its recommended algorithm and file shapes. If you open NUO: **Legacy / Export**, **Same as Original**. Rollback: Settings → **Traktor Pro 4 Native**.

## Four-track test

Path list: `m3u/nuo_queue_test4.m3u` (not committed). NUO does not ingest `.m3u`.

```bash
export PATH="$PWD/.venv/bin:$PATH"   # Homebrew Python 3.12; system 3.9 will fail
.venv/bin/python -m py.exec.separate --path m3u/nuo_queue_test4.m3u          # dry-run
.venv/bin/python -m py.exec.separate --path m3u/nuo_queue_test4.m3u --execute
.venv/bin/python -m py.exec.separate --path m3u/nuo_queue_known.m3u --limit 3 --execute
.venv/bin/python -m py.exec.separate --path m3u/nuo_queue_known.m3u --limit 25 --execute
```

Expect sibling `{name}.stem.m4a` (five AAC streams) plus Rekordbox `{name} - vocals.m4a` / `{name} - instrumental.m4a` when vocals have audio. Mute mixes print `we found none` and drop **both** pair files — the original mix is the instrumental.

Verbose logging is on: `log/{stamp}-py.exec.separate.log` plus a JSON sidecar (mutagen, vocals vs none, pass/fail, CPU/GPU/RSS samples) and matplotlib bars. `--quiet` skips that. `--execute` opens an Aqua progress window (filename, bar, live log, then the PNG reports) that stays until **Close**. Completion mails `david@alkalurops.org` via Mail.app with those PNGs attached (subject **STEMS separation — …**). `--no-gui` / `--no-notify` skip those. Needs `brew install python-tk@3.12`. PyQt is not used.

New files inherit source artist, title, album, label, BPM, key, and cover. STEM containers are tagged with MP4Box so the NI `stem` atom stays (mutagen would strip it). Cue points that exist only in Traktor’s NML are not in the audio file; embedded ID3 GEOB/PRIV is copied onto the pair.

```bash
.venv/bin/python -m py.exec.validate_meta --path m3u/nuo_queue_known.m3u           # QA
.venv/bin/python -m py.exec.validate_meta --path m3u/nuo_queue_known.m3u --execute  # repair
```

Traktor has no Reload Tag (that is Rekordbox). After a repair, right-click **Track Collection** in the Browser Tree → **Check Consistency**. If artist/title still show the filename, select the generated rows → **Delete from Collection** (do not check “additionally remove Traktor tags”) → Explorer → that folder → **Import to Collection**. Do not hand-edit `collection.nml`. Check Consistency on the whole library does not block `py.exec.separate` — it only refreshes NML for tracks already in the collection; new siblings are imported later.

Then, if you want loose role files:

```bash
.venv/bin/python -m py.exec.extract_stems --path ~/Music/stems_audio/16\ Bit\ Lolitas
.venv/bin/python -m py.exec.extract_stems --path ~/Music/stems_audio/16\ Bit\ Lolitas --execute
```

Add the new files from `stems_audio` in Traktor and Rekordbox when David wants. Do not hand-edit `collection.nml` or `master.db` from this repo. Log in `docs/PROGRESS.md`. No audio in git.

## Other tools

```bash
python3 -m py.tools.simple_mp3 convert --path ~/some/folder
python3 -m py.tools.tag_updater ~/some/folder --execute
python3 -m py.tools.trak_extract ~/some/folder -o ~/Extracted_Sets --execute
python3 -m py.utils.apple --path ~/some/folder --mode audio
python3 -m py.exec.cleanup_unknown
python3 -m py.exec.vocals_instrumental --path ~/Music/stems_audio --extract-only
python3 -m py.exec.validate_meta --path ~/Music/stems_audio
```

Deps: `pip install -r requirements.txt` (includes `py/exec/requirements.txt`). **MP4Box**: `brew install gpac`. **Progress window**: `brew install python-tk@3.12`. Model caches: Kimberley under `/tmp/audio-separator-models/`; 4-stem BS-RoFormer next to the `bs_roformer` package.

Headset MP3s stay in `SIMPLE_MP3` (or `--dest`). Apple-friendly output stays in `ip/` (or `--dest`). Neither writes `Media.localized`.

## Do not

- Commit `.stem.m4a`, WAV, FLAC, NML, `.trak`, `master.db`, or `m3u/*.m3u`.
- Flip NUO to Native without the rollback note.
- Write extracted stems into Apple Music.
- Open the blackhole repo to debug stems. Mixer stays over there.
- Run `--execute` on a whole drive without reading the dry-run first.
