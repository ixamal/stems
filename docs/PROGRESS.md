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
