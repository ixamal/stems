"""py.utils.catalog — dest paths under stems_audio and skip-if-present.

Keeps the DJ stem tree separate from Apple Music (Media.localized).
Duplicate detection is conservative: skip if the dest already exists,
or if the same artist/album/title/role is already on disk.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from mutagen import File as MutagenFile

from py.utils.paths import (
    CONFIG_DIR,
    STEMS_AUDIO,
    ensure_config_dir,
    is_audio,
    normalize_role,
    sanitize,
)

ROLE_SUFFIX = re.compile(
    r"(?:[\s_-]+|\s*\()(drums?|bass|other|highs?|instrumental|inst|melody|"
    r"acapellas?|vocals?|vox)\)?$",
    re.IGNORECASE,
)


def _first(tags, keys: tuple[str, ...]) -> str:
    for key in keys:
        values = tags.get(key)
        if values:
            return str(values[0])
    return ""


def strip_role_from_title(title: str) -> str:
    cleaned = ROLE_SUFFIX.sub("", title).strip(" -_")
    return cleaned or title


def role_from_name(name: str) -> str | None:
    stem = Path(name).stem
    match = ROLE_SUFFIX.search(stem)
    if not match:
        return None
    return normalize_role(match.group(1))


def read_tags(path: Path) -> tuple[str, str, str]:
    """Return (artist, album, title). Best-effort mutagen, then filename."""
    artist = album = title = ""
    try:
        audio = MutagenFile(path, easy=True)
        if audio is not None and audio.tags is not None:
            tags = audio.tags
            artist = _first(tags, ("albumartist", "artist"))
            album = _first(tags, ("album",))
            title = _first(tags, ("title",))
    except Exception:
        pass

    if not title:
        title = Path(path).stem

    artist = sanitize(artist, "Unknown Artist")
    album = sanitize(album, "Unknown Album")
    title = sanitize(title, path.stem)
    return artist, album, title


def audio_snapshot(path: Path) -> dict:
    """Mutagen + size snapshot for run JSON. Best-effort; never raises."""
    out: dict = {
        "path": str(path),
        "name": path.name,
        "exists": path.is_file(),
        "size_bytes": None,
        "artist": None,
        "album": None,
        "title": None,
        "genre": None,
        "date": None,
        "length_s": None,
        "bitrate": None,
        "sample_rate": None,
        "channels": None,
        "mime": None,
    }
    try:
        if path.is_file():
            out["size_bytes"] = path.stat().st_size
    except OSError:
        pass
    try:
        audio = MutagenFile(path, easy=True)
    except Exception as exc:
        out["error"] = str(exc)
        return out
    if audio is None:
        return out
    info = getattr(audio, "info", None)
    if info is not None:
        length = getattr(info, "length", None)
        bitrate = getattr(info, "bitrate", None)
        out["length_s"] = float(length) if length else None
        out["bitrate"] = int(bitrate) if bitrate else None
        rate = getattr(info, "sample_rate", None)
        out["sample_rate"] = int(rate) if rate else None
        channels = getattr(info, "channels", None)
        out["channels"] = int(channels) if channels else None
    mime = getattr(audio, "mime", None)
    if mime:
        out["mime"] = list(mime) if not isinstance(mime, str) else [mime]
    tags = audio.tags
    if tags is not None:
        out["artist"] = _first(tags, ("albumartist", "artist")) or None
        out["album"] = _first(tags, ("album",)) or None
        out["title"] = _first(tags, ("title",)) or None
        out["genre"] = _first(tags, ("genre",)) or None
        out["date"] = _first(tags, ("date", "year")) or None
    return out


@dataclass
class CatalogHit:
    path: Path
    artist: str
    album: str
    title: str
    role: str | None
    size: int


class StemCatalog:
    """Index of stems_audio plus dest-path planning."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root).expanduser().resolve() if root else STEMS_AUDIO
        self._by_key: dict[str, CatalogHit] = {}
        self._by_name: dict[str, CatalogHit] = {}
        self._loaded = False

    @staticmethod
    def identity_key(artist: str, album: str, title: str, role: str) -> str:
        base = strip_role_from_title(title)
        return "|".join(
            [
                artist.casefold(),
                album.casefold(),
                base.casefold(),
                role.casefold(),
            ]
        )

    def load(self) -> None:
        if self._loaded:
            return
        self._by_key.clear()
        self._by_name.clear()
        if self.root.is_dir():
            for path in self.root.rglob("*"):
                if not path.is_file() or path.name.startswith("."):
                    continue
                if not is_audio(path):
                    continue
                self._remember(path)
        self._loaded = True

    def _remember(self, path: Path) -> None:
        artist, album, title = read_tags(path)
        role = role_from_name(path.name) or normalize_role(
            title.split(" ")[-1] if title else None
        )
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        hit = CatalogHit(path, artist, album, title, role, size)
        if role:
            self._by_key[self.identity_key(artist, album, title, role)] = hit
        self._by_name[path.name.casefold()] = hit

    def destination(
        self,
        artist: str,
        album: str,
        title: str,
        role: str,
        ext: str,
    ) -> Path:
        artist = sanitize(artist, "Unknown Artist")
        album = sanitize(album, "Unknown Album")
        title = sanitize(strip_role_from_title(title), "Unknown Title")
        if not ext.startswith("."):
            ext = f".{ext}"
        filename = f"{title} - {role}{ext}"
        return self.root / artist / album / filename

    def existing(self, dest: Path, artist: str, album: str, title: str, role: str):
        if dest.exists():
            return dest
        self.load()
        hit = self._by_key.get(self.identity_key(artist, album, title, role))
        if hit:
            return hit.path
        named = self._by_name.get(dest.name.casefold())
        if named:
            return named.path
        return None

    def should_skip(
        self,
        dest: Path,
        artist: str,
        album: str,
        title: str,
        role: str,
        *,
        force: bool = False,
    ) -> tuple[bool, str]:
        if force:
            return False, ""
        existing = self.existing(dest, artist, album, title, role)
        if existing is None:
            return False, ""
        if existing.resolve() == dest.resolve() if dest.exists() else False:
            return True, f"already at dest ({existing.name})"
        return True, f"duplicate of {existing}"

    def note_written(self, dest: Path) -> None:
        if dest.exists():
            self._remember(dest)

    def write_manifest(self, jobs: list[dict], name: str = "extract_manifest.json") -> Path:
        ensure_config_dir()
        path = CONFIG_DIR / name
        payload = {
            "written_at": datetime.now(timezone.utc).isoformat(),
            "root": str(self.root),
            "jobs": jobs,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return path
