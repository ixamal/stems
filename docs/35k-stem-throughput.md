# Few days, not 92 — where to run the factory

Same Mel + BS-RoFormer CLI we already have. One GPU still does one track at a
time. “A few days” means many GPUs, each with a slice of the queue. The
current Mac batch (1905 writes) stays on `ix`.

Pace used here: 520/1905 writes in 985 min → **~3.8 min/track**. 35k × that is
**~2,210 GPU-hours**. NVIDIA may be faster; treat ~2× MPS as hopeful until one
CUDA track is proved.

| | |
|---|---|
| Best first farm | **RunPod Secure Cloud** |
| GPUs for ~3 days at this Mac’s pace | **31** |
| GPUs if NVIDIA is ~2× MPS | **16** |
| GPU rent for 35k (order of mag.) | **~$600–1,200** |

An L4 or RTX 4090 on RunPod Secure is the same class of NVIDIA card AWS g6 and
GCP L4 rent. PyTorch does not care who owns the rack. What you skip is IAM,
VPCs, Batch/GKE, and a support contract. What you accept: self-serve pods, you
bring Docker, **Secure Cloud not Community** (Community is peer-to-peer and can
vanish mid-job). Workspace Business Plus does not discount GCP GPUs.

Cursor canvas source (same numbers): [`35k-stem-throughput.canvas.tsx`](35k-stem-throughput.canvas.tsx).

## How the three farms compare for this job

| | RunPod Secure | GCP (L4 / Batch) | AWS (g6 + S3) |
|---|---|---|---|
| GPU quality | Same NVIDIA as the others | Same | Same |
| Price for 35k GPU-hr | Lowest (~$0.40–0.70/hr) | Mid (~$0.55–0.70) | Highest (~$0.80–1.00) + egress |
| Time to first GPU | Account + card, minutes | Project, billing, GPU quota (can be days) | Account, IAM, quota, VPC (often days) |
| 350 GB library | Network volume in one DC; pods attach it | GCS bucket; workers stream or cache | S3; workers stream or EFS |
| Stems back to `ix` | rsync / runpodctl / S3-compatible API | gsutil; egress billed | aws s3 sync; egress ~$0.09/GB |
| Push this git | Docker pull + git clone in the pod | Artifact Registry + Cloud Batch | ECR + Batch or ECS |
| Agent help | Dockerfile, shard M3U, worker cmd | Same image + Batch job JSON | Same image + more YAML |
| Fit for a few-day crate | **Best first try** | Fine if you already live in GCP | Overkill unless you need S3 forever |

On-demand L4 list (US, ~2026-08): RunPod Secure **$0.49/hr**, GCP `g2-standard-8`
**~$0.85/hr**, AWS `g6.xlarge` **~$0.80/hr**. Same 2,210 hours: about **$1,080**
vs **$1,560–1,890**, plus GCS/S3 egress on the way home.

## Wall clock to finish 35k

| Fleet | At Mac pace | If CUDA is ~2× MPS | GPU $ at ~$0.50/hr |
|---|---|---|---|
| 1 GPU (this Mac or one pod) | 92 days | 46 days | n/a or ~$1,100 |
| 8 GPUs | 11.5 days | 5.8 days | same hours, same $ |
| 16 GPUs (hopeful 3-day) | 5.8 days | ~3 days | ~$550 |
| 31 GPUs (same pace, 3-day) | ~3 days | ~1.5 days | ~$1,100 |

Dollars do not drop when you add GPUs — you spend the same GPU-hours in less
calendar time. 32 pods for 3 days is the same ~$1,100 as one pod for 92 days.
You pay for parallelism with operational fuss, not extra rent.

## What “push what we have” actually means

GitHub has the factory (`py.exec.separate`). Audio is not in git and must not
be. Two pipes:

**Code (git).** CUDA Dockerfile: Python 3.12, torch, ffmpeg, gpac,
audio-separator, this repo. Worker:
`python -m py.exec.separate --path /data/shards/017.m3u --execute --no-gui --no-notify`.
Split the queue into N M3U files (one per GPU). Prove one track on one RunPod
GPU before buying 30.

**Audio (350 GB).** Copy `stems_audio` to a RunPod network volume in one
region. Not `Media.localized`. Attach that volume to every pod in that
datacenter. When a shard finishes, rsync new `.stem.m4a` + pair files back to
`ix`. Output can be 2–4× the mix.

## Recommended try

1. **One Secure Cloud pod (half a day).** Network volume, our Docker image, one
   album. Confirm CUDA, MP4Box stem atom, tags, and minutes/track vs `ix`. If
   24 GB VRAM OOMs, step up to 48 GB.
2. **Scale to ~16–32 pods in that same DC.** Each pod gets one shard M3U. Same
   volume. Stop pods when the shard is done. Leave Community Cloud alone.
3. **Skip AWS/GCP until RunPod is boring.** Use GCP only if GPU quota is
   already approved. Do not start on AWS unless you want S3 as the long-term
   store.

Does not stop the current `ix` 1905-write run. Parked 2026-08-24.
