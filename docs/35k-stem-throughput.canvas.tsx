import {
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Stack,
  Stat,
  Table,
  Text,
} from "cursor/canvas";

/** Live ix pace: 520/1905 writes in 985 min, two writes per track. */
const MIN_PER_TRACK = (985 / 520) * 2;
const TRACKS = 35_000;
const GPU_HOURS_SAME = (TRACKS * MIN_PER_TRACK) / 60;
const GPU_HOURS_FAST = GPU_HOURS_SAME / 2;
const DAYS_TARGET = 3;
const GPUS_FOR_3_DAYS_SAME = Math.ceil(GPU_HOURS_SAME / (DAYS_TARGET * 24));
const GPUS_FOR_3_DAYS_FAST = Math.ceil(GPU_HOURS_FAST / (DAYS_TARGET * 24));

export default function StemThroughputCanvas() {
  return (
    <Stack gap={24}>
      <Stack gap={8}>
        <H1>Few days, not 92 — where to run the factory</H1>
        <Text tone="secondary">
          Same Mel + BS-RoFormer CLI we already have. One GPU still does one
          track at a time. “A few days” means many GPUs, each with a slice of
          the queue. Current Mac batch (1905 writes) stays on ix.
        </Text>
      </Stack>

      <Grid columns={4} gap={12}>
        <Stat value="RunPod Secure" label="Best first farm to try" tone="success" />
        <Stat value={`${GPUS_FOR_3_DAYS_SAME} GPUs`} label="For ~3 days at this Mac’s pace" />
        <Stat value={`${GPUS_FOR_3_DAYS_FAST} GPUs`} label="If NVIDIA is ~2× MPS" />
        <Stat value="~$600–1,200" label="GPU rent for 35k (order of mag.)" />
      </Grid>

      <Callout tone="info" title="RunPod compares on the chip, not on the paperwork">
        An L4 or RTX 4090 on RunPod Secure is the same class of NVIDIA card
        AWS g6 and GCP L4 rent. PyTorch does not care who owns the rack. What
        you skip is IAM, VPCs, Batch/GKE, and a support contract. What you
        accept: self-serve pods, you bring Docker, Secure Cloud not Community
        (Community is peer-to-peer and can vanish mid-job). For a private DJ
        crate this is enough. For a bank, it is not.
      </Callout>

      <H2>How the three farms compare for this job</H2>
      <Table
        headers={[
          "",
          "RunPod Secure",
          "GCP (L4 / Batch)",
          "AWS (g6 + S3)",
        ]}
        rows={[
          [
            "GPU quality",
            "Same NVIDIA as the others",
            "Same",
            "Same",
          ],
          [
            "Price for 35k GPU-hr",
            "Lowest (~$0.40–0.70/hr)",
            "Mid (~$0.55–0.70)",
            "Highest (~$0.80–1.00) + egress",
          ],
          [
            "Time to first GPU",
            "Account + card, minutes",
            "Project, billing, GPU quota (can be days)",
            "Account, IAM, quota, VPC (often days)",
          ],
          [
            "350 GB library",
            "Network volume in one DC; pods attach it",
            "GCS bucket; workers stream or cache",
            "S3; workers stream or EFS",
          ],
          [
            "Stems back to ix",
            "rsync / runpodctl / S3-compatible API",
            "gsutil; egress billed",
            "aws s3 sync; egress ~$0.09/GB",
          ],
          [
            "Push this git",
            "Docker pull + git clone in the pod",
            "Artifact Registry + Cloud Batch",
            "ECR + Batch or ECS",
          ],
          [
            "I can help you",
            "Dockerfile, shard M3U, worker cmd",
            "Same image + Batch job JSON",
            "Same image + more YAML",
          ],
          [
            "Fit for a few-day crate",
            "Best first try",
            "Fine if you already live in GCP",
            "Overkill unless you need S3 forever",
          ],
        ]}
        striped
      />

      <H2>Wall clock to finish 35k</H2>
      <Text tone="secondary" size="small">
        35k × 3.8 min/track ≈ 2,210 GPU-hours at this Mac’s pace. NVIDIA may
        be faster; use the 2× column as hopeful, not promised, until we prove
        one CUDA track.
      </Text>
      <Table
        headers={["Fleet", "At Mac pace", "If CUDA is ~2× MPS", "GPU $ at ~$0.50/hr"]}
        columnAlign={["left", "right", "right", "right"]}
        rows={[
          ["1 GPU (this Mac or one pod)", "92 days", "46 days", "n/a or ~$1,100"],
          ["8 GPUs", "11.5 days", "5.8 days", "same hours, same $"],
          [`${GPUS_FOR_3_DAYS_FAST} GPUs (hopeful 3-day)`, hoursLabel(GPU_HOURS_SAME / GPUS_FOR_3_DAYS_FAST), `~${DAYS_TARGET} days`, `~$${Math.round(GPU_HOURS_FAST * 0.5).toLocaleString()}`],
          [`${GPUS_FOR_3_DAYS_SAME} GPUs (same pace, 3-day)`, `~${DAYS_TARGET} days`, "~1.5 days", `~$${Math.round(GPU_HOURS_SAME * 0.5).toLocaleString()}`],
        ]}
        rowTone={["neutral", "info", "success", "warning"]}
        striped
      />
      <Text tone="tertiary" size="small">
        Dollars do not drop when you add GPUs — you spend the same GPU-hours
        in less calendar time. 32 pods for 3 days is the same ~$1,100 as one
        pod for 92 days. You pay for parallelism with operational fuss, not
        extra rent.
      </Text>

      <H2>What “push what we have” actually means</H2>
      <Text>
        GitHub already has the factory (py.exec.separate). Audio is not in
        git and must not be. Cursor writes the Docker image and the shard
        worker; you upload the crate to a volume. Two pipes, not one.
      </Text>
      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader trailing={<Pill tone="success" active>I do this with you</Pill>}>
            Code (git)
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text>
                1. CUDA Dockerfile: Python 3.12, torch, ffmpeg, gpac,
                audio-separator, this repo.
              </Text>
              <Text>
                2. Worker entry: python -m py.exec.separate --path
                /data/shards/017.m3u --execute --no-gui --no-notify
              </Text>
              <Text>
                3. Split the queue into N M3U files (one per GPU). Skip
                complete sets as we do now. Later: skip already-acappella.
              </Text>
              <Text tone="secondary" size="small">
                Prove one track on one RunPod GPU before buying 30.
              </Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill tone="warning" active>You do this on the wire</Pill>}>
            Audio (350 GB)
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Text>
                1. Copy the crate to a RunPod network volume in one region
                (or GCS/S3). Not Media.localized — stems_audio tree only.
              </Text>
              <Text>
                2. Attach that volume to every pod in that datacenter.
              </Text>
              <Text>
                3. When a shard finishes, rsync new .stem.m4a + pair files
                back to ix. Output can be 2–4× the mix.
              </Text>
              <Text tone="secondary" size="small">
                Home gigabit: 350 GB up is hours if the line is real. AWS
                download of ~1 TB is the extra ~$90 tax. RunPod rsync home
                avoids that tax.
              </Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <H2>Recommended try — three days, not a new career</H2>
      <Stack gap={10}>
        <H3>1. One Secure Cloud pod (half a day)</H3>
        <Text>
          Network volume, our Docker image, one album. Confirm CUDA, MP4Box
          stem atom, tags, and minutes/track vs ix. If VRAM OOMs, step up
          from 24 GB (4090/L4) to 48 GB.
        </Text>
        <H3>2. Scale to ~16–32 pods in that same DC (the few-day pass)</H3>
        <Text>
          Each pod gets one shard M3U. Same volume. Stop pods when the shard
          is done so the disk bill does not double on idle. Leave Community
          Cloud alone for this crate.
        </Text>
        <H3>3. Skip AWS/GCP until RunPod is boring</H3>
        <Text>
          If you already have a GCP org and GPU quota, we can use the same
          image there instead. Do not start on AWS unless you want S3 as
          the long-term store — you will spend more calendar time on IAM
          than on stems.
        </Text>
      </Stack>

      <Divider />
      <Text tone="tertiary" size="small">
        Does not stop the current ix 1905-write run. Next crate: acappella
        skip + optional RunPod proof track.
      </Text>
    </Stack>
  );
}

function hoursLabel(h: number): string {
  if (h >= 24) return `${(h / 24).toFixed(1)} days`;
  return `${Math.round(h)} h`;
}
