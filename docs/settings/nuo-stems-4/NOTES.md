# NUO-STEMS 4

Version seen: **4.0.0**. Licensed on this Mac 2026-08-23.

**Credit.** [NUO-STEMS](https://nuo-stems.com) is Alex’s product (DJ NUO). The recommended split (`mel_vocals_bs_others`), sibling `{name}.stem.m4a` next to the mix, Rekordbox vocals/instrumental pair, and NI STEM container are the functions we matched. That work is what made a local factory thinkable.

**Why a CLI anyway.** Alex has no CLI planned, and the app does not ingest `.m3u`. David’s library is **35k+** tracks. GUI drop of four files proved the idea; GUI drop of tens of thousands is not a shop. This repo’s job is unattended batch: `python3 -m py.exec.separate` over `m3u/` path lists. NUO stays licensed on `ix` for comparison and for one-off GUI work.

## Mode

**Legacy / Export** as of 2026-08-23. Native was the first-launch pick; the crate and extract tools already assume sibling `.stem.m4a`, and Native hides M3U drop.

| Mode | Use |
|------|-----|
| Legacy / Export | This Mac. `{name}.stem.m4a` next to the original. Default. |
| Traktor Pro 4 Native | Linked `{hash}.stem.mp4` in Traktor’s Stems folder. Parked. |
| DAW / Non-Traktor | Individual WAV/FLAC. Later. |

**Rollback to Native:** NUO Settings → mode → Traktor Pro 4 Native. Existing `.stem.m4a` files stay. Do not delete `~/Music/Traktor/Stems/`.

**Legacy settings for this crate (2026-08-23):**

- Output to original folder: **ON** (`/Users/david/Downloads` is only the fallback)
- Save .wav / Keep WAV/FLAC: **OFF**
- Save Instrumental & Acapella: **ON** (NUO writes the Rekordbox pair; `py.vocals_instrumental` skips if those siblings exist)
- Encoding for that pair: prefer **AAC @ 256 kbps** (NI’s stem default). Not WAV. MP3 320 is fine if AAC is not in the dropdown
- Algorithm: **`mel_vocals_bs_others`** (recommended). Local CLI matches that: Kimberley Mel vocals + ZFTurbo 4-stem **`bs_roformer`** for drums/bass/other, muxed to `{name}.stem.m4a`. `bs_roformer` alone is close; Mel vocals stay when they have audio.
- Sum of stems = original mix: **ON** (DJ)

M3U is **our** shopping list only (`m3u/`, not `config/`) — NUO rejected `nuo_queue_test4.m3u` (“File format is not supported”). In the GUI, drop the **audio files** (mp3/wav/m4a/aif/flac), or NUO’s Select Files. Local generation is `python3 -m py.exec.separate`.

## Native (parked)

Traktor Preferences `Browser.Dir.GeneratedStems`: `~/Music/Traktor/Stems/`. Empty as of 2026-08-23. Not Apple Music, not `stems_audio`. Native ignores NUO’s output folder and hides queue drag-and-drop. Tracks must already be in `collection.nml`.

**If David jams and hits Traktor Generate Stems:** leave the hash file. Harvest later (MASTER_CONTEXT §7).

## Load (Legacy)

NUO does **not** ingest M3U. Path lists: `m3u/nuo_queue_test4.m3u` (proved), `m3u/nuo_queue_known.m3u`, then the rest of the 35k+. Local generation: `python3 -m py.exec.separate`.
