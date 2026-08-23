"""Machine paths and filename rules.

stems_audio is the DJ stem tree. Apple Music lives elsewhere
(Media.localized) and is not written by this package.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"

STEMS_AUDIO = Path.home() / "Music" / "stems_audio"
APPLE_MUSIC_MEDIA = Path.home() / "Music" / "Music" / "Media.localized"
SIMPLE_MP3_DIRNAME = "SIMPLE_MP3"

STEM_CONTAINERS = (".stem.m4a", ".stem.mp4", ".stem.mp3")
AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".aiff",
    ".aif",
    ".flac",
    ".m4a",
    ".aac",
    ".alac",
    ".ogg",
    ".wma",
    ".mp4",
}

# Native Instruments STEM stream map (0 = mix / master).
# Names match how David wants crates to read.
STEM_ROLES = {
    1: "drums",
    2: "bass",
    3: "other",
    4: "acapella",
}
ROLE_ALIASES = {
    "drums": "drums",
    "drum": "drums",
    "bass": "bass",
    "other": "other",
    "highs": "other",
    "high": "other",
    "inst": "other",
    "melody": "other",
    "instrumental": "instrumental",
    "acapella": "vocals",
    "acapellas": "vocals",
    "vocals": "vocals",
    "vocal": "vocals",
    "vox": "vocals",
}

# Vocals = stream 4. Instrumental = drums+bass+other (not stream 3 alone).
# Written parallel to the .stem.m4a as AAC for Rekordbox.
PAIR_ROLES = ("vocals", "instrumental")
SOURCE_TRACK_EXTS = {".mp3", ".m4a", ".wav", ".aiff", ".aif", ".flac", ".aac"}
SKIP_PATH_PARTS = {
    "_rescued_from_staging",
    "_quarantine",
    "Library",
    ".shortcut-targets-by-id",
}

INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def sanitize(part: str, fallback: str) -> str:
    """Same filesystem rules as music_migration.stems.organize_stems."""
    text = (part or "").strip()
    text = INVALID_FS_CHARS.sub("_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or fallback


def is_stem_container(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(suffix) for suffix in STEM_CONTAINERS)


def is_audio(path: Path) -> bool:
    if is_stem_container(path):
        return True
    return path.suffix.lower() in AUDIO_EXTENSIONS


def container_basename(path: Path) -> str:
    name = path.name
    lower = name.lower()
    for suffix in STEM_CONTAINERS:
        if lower.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def normalize_role(name: str | None) -> str | None:
    if not name:
        return None
    return ROLE_ALIASES.get(name.strip().lower())


def skip_tree(path: Path) -> bool:
    return any(part in SKIP_PATH_PARTS for part in path.parts)


def sibling_stem(track: Path) -> Path | None:
    """Same-folder `{name}.stem.m4a` / `.stem.mp4` / `.stem.mp3`."""
    for suffix in STEM_CONTAINERS:
        candidate = track.with_name(f"{track.stem}{suffix}")
        if candidate.exists():
            return candidate
    return None
