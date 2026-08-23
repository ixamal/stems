# Progress

Session notes. I direct. Agent lifts. We write it down.

---

## 2026-08-22 — Repo stood up

Left blackhole parked (`a2ad27e`). New house for stems.

NUO-STEMS 4.0.0 welcome screen: three modes. Picked the plan, not the click yet.

**Call:** Traktor Pro 4 Native. Same Mac as Traktor 4.5.1. Understand, then one track.

Legacy is for a different computer. DAW is WAV/FLAC for later (Maschine). Demo Mode is enough to prove the pipe.

Next chat opens *this* folder. Don’t reopen blackhole for stem clicks.

---

## 2026-08-22 — py/ ports + catalog

Brought David’s older utilities from [davidrichardnelson/music](https://github.com/davidrichardnelson/music) into `py/` as classes. Language folder is `py/` so later languages can sit beside it.

**Pipe:** NUO **Traktor Pro 4 Native** (that welcome modal — Understand, not Show Later) → `.stem.m4a` / `.stem.mp4` → `StemExtractor` → `~/Music/stems_audio/{Artist}/{Album}/{Title} - {role}.m4a` with roles drums / bass / other / acapella. M4A default so Traktor is happy. Dry-run unless `--execute`. Same Artist/Album sanitize as music_migration so we land in the existing tree instead of making a second catalog.

**Dedup:** skip if dest exists or artist+album+title+role is already under stems_audio. `--force` to overwrite.

**Stay out of Apple Music.** `AppleFriendly` refuses `Media.localized`. Headset 320k (`SimpleMp3`) writes `SIMPLE_MP3`, not stems_audio. No NML / `master.db` writes here — add the new files in Traktor/Rekordbox, remaps stay in music_migration.

Also ported: `TagUpdater`, `TrakExtractor`. `ffmpeg` is on `ix` (9.0.1). Need: prove one Native track, then dry-run extract on that folder so we learn where NUO actually writes.

---

## 2026-08-22 — Quarantine nameless role WAVs

`Unknown Artist/Unknown Album` had 1,641 files. Cleared the ones with no track identity: `bass.wav` / `bass (N).wav` and the same for drums / other / vocals. **968 WAVs, ~54 GB.** Pattern only — Bassnectar MP3s and the other 673 named files stayed.

Moved, not deleted: `~/Music/stems_audio/_quarantine/2026-08-22-unknown-role-wavs/`. Rollback: move them back. If Traktor still lists `bass (159).wav`, that entry is a ghost until we remap or drop it in music_migration.

`python3 -m py.cleanup_unknown` (dry-run) / `--execute`. Folder still has real orphans that *have* titles — Queen `_vocals.m4a`, mashups, `.stem.m4a` with no tags. Those need a later pass, not a blind wipe.

**WAV headers (quarantine pile):** 964/968 are `fmt` + `data` only — no ID3, no RIFF INFO, no BWF. The other four have LIST INFO with `INAM` = `bass`/`drums`/`other`/`vocals` plus a Traktor `NITR`/`NTKB` analysis blob (not a title). All 44.1 kHz / 16-bit / stereo. Titles are not recoverable from metadata.

David deleted the quarantine pile after that check. `_quarantine/` is gone. No rollback. Unknown Album still has the 673 named orphans. If Traktor still lists `bass (159).wav`, those entries are ghosts.

**Inventory (stems_audio, 2,914 files):** `.stem.m4a` / `.stem.mp4` / `.stem.mp3` are **containers** (1,090) — four streams in one file, not split. Loose `.m4a` is rare (28): 23 are `_vocals.m4a`, 5 are plain tracks. Most of the tree is full `.mp3` (1,679) plus containers waiting to be extracted. 340 album folders have a container and no role parts yet. 93 folders have both a container and a vocals (etc.) sidecar.

---

## 2026-08-22 — Vocals + instrumental pair

`python3 -m py.vocals_instrumental`. If a STEM exists: **acapella** = stream 4 AAC copy (same bits as the m4a). **instrumental** = drums+bass+other mixed to **ALAC** in `.m4a`. Skip if `(acapella)` / `(instrumental)` already sit next to it (Metallica did). If no STEM: `config/nuo_queue.m3u` for NUO-STEMS 4. NUO has no CLI — drag the playlist; leave Native on. Do not `--execute` the whole tree (`--limit`).

**Aligned with David:** `.stem.m4a` stays for Traktor. Parallel AAC `{name} - vocals.m4a` + `{name} - instrumental.m4a` (mix minus vocals) for Rekordbox. Default is inplace AAC, not ALAC / not tag-catalog rename.

**Test — 03 Mindphaser.stem.m4a:** stem mtime unchanged. Wrote `03 Mindphaser - vocals.m4a` (AAC copy of stream 4) and `03 Mindphaser - instrumental.m4a` (AAC mix of 1+2+3). Both played via `afplay`. Second pass skipped. First instrumental write failed (STEM has an h264 waveform stream) — fixed with `-vn` / `-map [mix]`.

---

## 2026-08-22 — Numbered Finder dupes

`python3 -m py.cleanup_numbered`. Rule: trash `Name (2).ext` / `(3)` only when un-numbered original exists **and sizes match**. **177** files → `~/.Trash`. Second pass: nothing to do.

FLA `(2)` stems stayed: `ls` says 55M/45M/57M but bytes differ from the Aug 21 originals (e.g. Final Impact (2) 57,737,959 vs original 57,150,769). `Final Impact - acapella.m4a` / ALAC instrumental are leftover from the first extract test, not `(2)` copies.

**Tolerance pass 0.005 (0.5%):** trashed **40** near-misses. **207** numbered siblings stay — ratio above 0.005. FLA Tactical `(2)` files are 0.0087–0.0118 (need ~0.012 to catch them). Manifest: `config/numbered_dupe_cleanup.json`.

**Raised to 0.012.** Trashed **80** more (incl. Final Impact / Mindphaser / Gun `(2)`). **127** still out: 26 at 0.012–0.020, 66 at 0.020–0.050, 35 above 0.050 (max 12.44). Default `--tolerance` is now 0.012. FLA Tactical folder has no numbered stems left. `Final Impact - acapella.m4a` / ALAC instrumental leftovers still there.

**Raised to 0.05 (go big).** Trashed **92** more. **35** left — real size gaps, not Finder clones. Worst: TKK `These Remains (2)/(3)` vs a 4 MB original (ratio **12.44**). Default `--tolerance` is 0.05.

---

## 2026-08-22 — Vocals/instrumental across stems_audio

`python3 -m py.vocals_instrumental --path ~/Music/stems_audio --extract-only --execute`

**1355/1355 ok, 0 fail, 339 skip** (already had a sibling). ~50 min. Did not touch `.stem.m4a`. Did not write NUO queue.

Wrote AAC next to each container: `{base} - vocals.m4a` (stream 4 copy) and `{base} - instrumental.m4a` (1+2+3 mix, 256k). Spot-check (Bargeld, Everyday Is Exactly The Same, Gorgeous Mighty Mouse, Venture New Dawn, Failbait): codec `aac`, none 0-byte. Second dry-run: **0 extract / 1694 skip**.

Coverage now: 608 ` - vocals.m4a`, 750 ` - instrumental.m4a`. Some STEMs only needed the mix (vocals already sat as `_vocals` / `(acapella)` / `.mp3`). Metallica / Queen / Lords of Acid already had `(acapella).mp3` + `(instrumental).mp3` — skipped on purpose. `Final Impact - acapella.m4a` / ALAC leftovers still there.

---

## 2026-08-22 — NUO queue for tracks with no STEM

`python3 -m py.vocals_instrumental --path ~/Music/stems_audio --queue-only --execute`

**910** source files have no `.stem.m4a` sibling: 862 mp3, 45 wav, 2 m4a, 1 aif. None of them already have a vocals/instrumental pair. Wrote `config/nuo_queue.m3u` (drag into NUO-STEMS 4; app has no CLI). Also `config/nuo_queue_known.m3u` — same list minus **464** `Unknown Artist` (452 of those are the Unknown Album dump).

Native will **not** drop a container next to the MP3. FAQ: `{hash}.stem.mp4` goes in Traktor’s Stems folder. Same-folder `.stem.m4a` is Legacy / Export. Mode stays Native until David says otherwise. Demo limits still unknown — don’t dump all 910 in one go.

---

## 2026-08-22 — Parked (license transfer)

David emailed NUO to move the license onto this Mac. Quit for the night. Do not drag `nuo_queue.m3u` until the app is licensed (Demo limits unknown).

**Done:** `py/` tools; numbered-dupe cleanup (tolerance 0.05); vocals/instrumental AAC across existing STEMs (1355/1355); NUO queue written locally (not in git).

**Next chat:** license lands → prove one Native generate → log the Stems folder path → then a small known-queue drag, not all 910. Rekordbox/Traktor import of the AAC pairs is manual whenever David wants; no quit required. Leave Native on.

---

## 2026-08-23 — License on this Mac

NUO-STEMS 4 is licensed. Next is **one** Native generate (Traktor open, mode stays Native). Stems dir is `~/Music/Traktor/Stems/` (empty). Do not drag the 910/446 queues until one file has landed there. Existing AAC pairs can wait; they are already on disk.

---

## 2026-08-23 — Skip Traktor Generate Stems (except jams)

Forego Traktor’s **Generate Stems** as the pipeline. NUO Native is the generator. If a session still uses the Traktor button, those files already go to `~/Music/Traktor/Stems/{nnn}/{hash}.stem.mp4` — same tree we harvest. Parked: scan that folder, map AUDIO_ID back to the original in `stems_audio`, write the Rekordbox pair. Do not rename hash files. If Traktor overwrote a NUO stem, re-queue in NUO.

---

## 2026-08-23 — Four-track Native test

`config/nuo_queue_test4.m3u` (not in git). Native cannot take an M3U drop. Import the four MP3s into Traktor first, then Generate STEMS from NUO’s Track Collection — not the empty Stems playlist (that is why the table said no rows). 435/446 known-queue files are not in `collection.nml` yet.

---

## 2026-08-23 — Switch to Legacy

Native is the circuitous path: quit NUO, import M3U into Traktor, quit Traktor to flush NML, relaunch NUO, hunt Track Collection. That is required because Native hides queue drop and only sees `collection.nml`.

**Call:** **Legacy / Export** + **Same as Original**. Writes `{name}.stem.m4a` next to the MP3 — the tree we already extract. Drop `nuo_queue_test4.m3u` on NUO. Traktor can stay out of it. Rollback: Settings → Native. Existing sibling STEMs stay.

NUO will also write instrumental + acapella when that toggle is on (built for Rekordbox/Serato/Denon). Algorithm: keep **`mel_vocals_bs_others`**. Encoding: **AAC 256**, not WAV; MP3 320 only if AAC is missing from the dropdown. No CLI from Alex — M3U is our path list; NUO rejected the playlist drop (“File format is not supported”). Drop the MP3s instead.

---

## 2026-08-23 — Own separator CLI

NUO will not take an M3U. `python3 -m py.separate` reads the list, skips existing pairs, runs [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) with Kimberley Jensen’s [Mel-Band-RoFormer](https://github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model). That checkpoint is **vocals + instrumental**, AAC 256k next to the source — the Rekordbox pair. A Traktor `.stem.m4a` is four stems muxed with NI metadata ([Stemgen](https://github.com/axeldelafosse/stemgen)); NUO’s recommended algorithm is Mel vocals *plus* BS-RoFormer drums/bass/other. Install: `pip install -r requirements-ml.txt`. Dry-run of the four-pack: 4 separate / 0 skip.

---

## 2026-08-23 — Four-pack proved on MPS

`.venv` is Homebrew Python 3.12 (system 3.9 cannot install audio-separator). Torch 2.13 arm64, MPS. Model cache `/tmp/audio-separator-models/`. Pin `librosa>=0.10,<1.0` — 1.x dropped `get_duration(filename=)` and crashed the M4A write. Kimberley residual stem is named **`other`**, not Instrumental; `py.separate` maps both.

`--execute` on `config/nuo_queue_test4.m3u`: **4/4 ok**. ~55s/track after the first model load. All eight files `codec=aac`, 44.1 kHz stereo, duration matches the MP3. Instrumentals ~266–276 kbps. Vocals are sparser (134–185 kbps) except **95 North mute mix** (0.2 MB / 4 kbps) — almost no voice, which fits the mix. Second pass skipped the first track as expected.

Do not dump the 446/910 queues yet. Listen to the four pairs first.

---

## 2026-08-23 — `.stem.m4a` + empty-vocals drop

NUO recommended is still **`mel_vocals_bs_others`**. `bs_roformer` is the 4-stem ZFTurbo checkpoint (`model_bs_roformer_ep_17_sdr_9.6568.ckpt`) — drums/bass/other/vocals in one pass. We mux with MP4Box (`brew install gpac`) into `{name}.stem.m4a` next to the MP3. Kimberley Mel vocals stay in the container when they have audio.

Empty Rekordbox vocals: if bitrate/size says near-silence, print **`we found none`** and delete. 95 North mute mix deleted. Instrumental stays. Traktor container still has a vocals stream (BS-RoFormer / silence) so the fourth deck exists.

`--execute` on the four-pack: **4/4 containers**, five AAC streams each, ~3 min/track on MPS (lossless residual pass). 16 Bit Lolitas 57 MB; 95 North 70 MB; AirBorn / Ananda 63 MB. MP4Box + `stem` udta atom. Do not dump 446 yet — play these in Traktor first.

---

## 2026-08-23 — Traktor OK; drop empty-pair instrumental; package layout

Four `.stem.m4a` files played in Traktor Pro 4. We're in the business.

**Empty vocals → no Rekordbox pair.** The original mix already is the instrumental. `py.exec.separate` now deletes both `{name} - vocals.m4a` and `{name} - instrumental.m4a` when vocals have no significant audio. 95 North leftover instrumental is the spot check.

**Layout:** `py/exec` (factory + `requirements.txt`), `py/utils` (ffmpeg, paths, catalog, apple guard, extraction map), `py/tools` (headset / tags / trak). Root `requirements.txt` is `-r py/exec/requirements.txt`. Playlists moved to `m3u/` parallel to `config/`.

---

## 2026-08-23 — Credit Alex; CLI is the 35k+ shop

Notes now say the quiet part: [NUO-STEMS](https://nuo-stems.com) (Alex / DJ NUO) is the licensed reference. `mel_vocals_bs_others`, sibling `{name}.stem.m4a`, and the Rekordbox pair are the functions we matched — that work made this factory possible. Alex has no CLI planned and the app rejects `.m3u`. David’s library is **35k+**. Four tracks in Traktor proved the pipe; the remaining work is unattended `py.exec.separate` over `m3u/` lists, not GUI drop.

---

## 2026-08-23 — Run logger + matplotlib

Every `py/` CLI writes `log/{stamp}-{tool}.log` by default (`--verbose`). JSON sidecar points at that log and records each source: mutagen snapshot, vocals vs none, instrumental kept/dropped, pass/fail, no-audio, process-tree CPU/RSS and parent Torch MPS bytes, timestamps. End of batch reads the JSON and draws bar charts (wall time, seconds per audio minute, CPU/RSS/GPU, vocals vs none). `--quiet` skips files. `log/` is not gitignored yet so the four-pack dry-run is a public example.

---

## 2026-08-23 — Next 10 from known queue

`--limit` now counts tracks that still need work. Vocals/acapella + instrumental + `.stem.m4a` is a complete set and is skipped unless `--force`. Four-pack (and 95 North mute) skipped; **10/10 pass** from `m3u/nuo_queue_known.m3u` (`--execute`, ~33 min, all vocals present). Log: `log/2026-08-23T175842Z-py.exec.separate.*`.

---

## 2026-08-23 — Copy source tags; QA module

Generated pair + `.stem.m4a` were landing with empty artist/label (Traktor showed filename-only rows). `py.utils.meta` copies artist, title, album, label, BPM, key, cover, ISRC, comments, and embedded cue GEOB from the source. STEM files use `MP4Box -itags` — mutagen `save()` strips the NI `stem` udta atom. `python3 -m py.exec.validate_meta` reports mismatches; `--execute` repairs. Ran on the known-queue siblings: **40/40 ok**. Traktor shows them after **Check Consistency**.

---

## 2026-08-23 — Progress HUD, notify, overlay charts

`--execute` opens an Aqua ttk window (filename, determinate bar, live verbose log) — tkinter, not PyQt (`brew install python-tk@3.12`). End of batch: Notification Center banner (Continuity can mirror to iPhone). Tracks chart overlays time-per-file bars + cumulative elapsed, X = source filename. `--no-gui` / `--no-notify` skip.

Proved on the next 3 from `m3u/nuo_queue_known.m3u`: **3 pass / 14 skip**, 6 writes, ~11 min. Log: `log/2026-08-23T185638Z-py.exec.separate.*`.

---

## 2026-08-23 — Gmail notify; HUD stays until Close

Cloud-agent iPhone ping parked. `--execute` mails `david@alkalurops.org` via Mail.app (plus a Mac banner). Progress window stays until **Close**. `compare_tags` now also requires comment, key, album artist, genre, date when the source has them. Post-process on everything generated so far: **0 mismatch / 49 ok** (`m3u/nuo_queue_known.m3u`) and **0/10** on the four-pack.

Rekordbox pair files were not getting `covr` (MP4Box `cover=` does not stick on those AAC files; Traktor reads mutagen). Pair tagging now uses mutagen. 95 North Barbie Dance vocals/instrumental repaired from the sibling STEM (cover + BPM + key). Traktor still shows the pre-stamp NML cache until **Check Consistency** (or delete-from-collection then re-import). There is no Reload Tag in Traktor 4.5.

End-of-run tracks/overview PNGs show in the progress window and attach to the Gmail.

---

## 2026-08-23 — Check Consistency vs factory; 25-track check before the tree

Traktor **Check Consistency** on the whole collection only reads existing NML paths and refreshes that cache. It does not lock `stems_audio`, and it does not import new siblings. The CLI can keep writing `{name}.stem.m4a` + Rekordbox pairs while it runs. New files stay out of Traktor until Explorer → Import (or a later consistency pass that already knows them).

Generated files on disk were already tagged; Traktor showed filename/empty artist until Check Consistency. There is no Reload Tag in Traktor 4.5 (that is Rekordbox).

**TODO later:** catalog the entire library into JSON with all metadata, and a webpage spreadsheet of it. Not now.

Next: `--limit 25 --execute` from `m3u/nuo_queue_known.m3u` so David can check those in Traktor before the rest of the crate.
