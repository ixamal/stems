# m3u/

Local path lists. **Not committed** (absolute paths on `ix`). Parallel to `config/` so JSON manifests stay out of the playlist pile.

| File | What |
|------|------|
| `nuo_queue.m3u` | Tracks under `stems_audio` with no sibling `.stem.m4a` |
| `nuo_queue_known.m3u` | Same list minus Unknown Artist |
| `nuo_queue_test4.m3u` | Four-pack used to prove Mel + BS-RoFormer |

NUO-STEMS 4 does not ingest `.m3u` (Alex: no CLI planned). These files are shopping lists for `python3 -m py.exec.separate --path m3u/…` — the path that scales to a 35k+ library.
