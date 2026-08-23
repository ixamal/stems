"""py.utils.meta — copy source tags onto generated M4A / STEM files.

Traktor, Rekordbox, and Music.app read artist, label, BPM, key, cover, and
title from the file. audio-separator and MP4Box write almost none of that.

**Pair files** (``{name} - vocals.m4a``): mutagen MP4 tags, including ``covr``
cover, tempo, key, LABEL. MP4Box ``cover=`` does not reliably land on the
Rekordbox pair; Traktor reads mutagen ``covr``.

**STEM containers** (``{name}.stem.m4a``): mutagen ``save()`` drops the NI
``stem`` udta atom (Traktor then stops seeing four decks). We tag those
with ``MP4Box -itags`` so the atom stays.

Cue points that live only in ``collection.nml`` are not in the audio file;
this copies what *is* embedded (ID3 GEOB/PRIV/CHAP, comments, BPM, key).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm

from py.utils.paths import is_stem_container

# Fields Traktor / Rekordbox / Music.app actually show.
REQUIRED_FIELDS = (
    "artist",
    "albumartist",
    "title",
    "album",
    "label",
    "bpm",
    "key",
    "comment",
    "cover",
)


class MetaError(RuntimeError):
    pass


def _mp4box() -> str:
    path = shutil.which("MP4Box")
    if not path:
        raise MetaError("MP4Box not on PATH. brew install gpac")
    return path


def _text(frame: Any) -> str:
    text = getattr(frame, "text", None)
    if text:
        return str(text[0]).strip()
    return str(frame).strip()


def _first_id3(tags: ID3, *keys: str) -> str:
    for key in keys:
        frames = tags.getall(key) if hasattr(tags, "getall") else []
        if not frames:
            frame = tags.get(key)
            frames = [frame] if frame is not None else []
        for frame in frames:
            value = _text(frame)
            if value:
                return value
    return ""


@dataclass
class SourceMeta:
    """Canonical tags pulled from an MP3 / M4A / AIFF source."""

    artist: str = ""
    albumartist: str = ""
    album: str = ""
    title: str = ""
    label: str = ""
    grouping: str = ""
    genre: str = ""
    date: str = ""
    bpm: str = ""
    key: str = ""
    track: str = ""
    isrc: str = ""
    comment: str = ""
    encoder: str = ""
    composer: str = ""
    copyright: str = ""
    url: str = ""
    cover_bytes: bytes = b""
    cover_mime: str = ""
    extras: dict[str, str] = field(default_factory=dict)
    geob: list[tuple[str, bytes]] = field(default_factory=list)
    priv: list[tuple[str, bytes]] = field(default_factory=list)

    def titled(self, suffix: str | None) -> str:
        base = self.title or ""
        if not suffix:
            return base
        return f"{base} - {suffix}" if base else suffix


def read_source_meta(path: Path) -> SourceMeta:
    """Best-effort dump. Never raises."""
    meta = SourceMeta()
    path = Path(path)
    try:
        easy = MutagenFile(path, easy=True)
        if easy is not None and easy.tags is not None:
            tags = easy.tags

            def grab(*keys: str) -> str:
                for key in keys:
                    values = tags.get(key)
                    if values:
                        return str(values[0]).strip()
                return ""

            meta.artist = grab("artist", "albumartist")
            meta.albumartist = grab("albumartist") or meta.artist
            meta.album = grab("album")
            meta.title = grab("title")
            meta.label = grab("organization", "label", "publisher")
            meta.grouping = grab("grouping")
            meta.genre = grab("genre")
            meta.date = grab("date", "originaldate", "year")
            meta.bpm = grab("bpm")
            meta.key = grab("initialkey", "key")
            meta.track = grab("tracknumber")
            meta.isrc = grab("isrc")
            meta.comment = grab("comment")
            meta.encoder = grab("encodedby")
            meta.composer = grab("composer")
            meta.copyright = grab("copyright")
            meta.url = grab("website")
    except Exception:
        pass

    try:
        id3 = ID3(path)
    except (ID3NoHeaderError, Exception):
        id3 = None
    if id3 is not None:
        meta.artist = meta.artist or _first_id3(id3, "TPE1")
        meta.albumartist = meta.albumartist or _first_id3(id3, "TPE2") or meta.artist
        meta.album = meta.album or _first_id3(id3, "TALB")
        meta.title = meta.title or _first_id3(id3, "TIT2")
        meta.label = meta.label or _first_id3(id3, "TPUB")
        meta.grouping = meta.grouping or _first_id3(id3, "TIT1")
        if not meta.label and meta.grouping:
            meta.label = meta.grouping
        meta.genre = meta.genre or _first_id3(id3, "TCON")
        meta.date = meta.date or _first_id3(id3, "TDRC", "TDOR", "TDRL", "TYER")
        meta.bpm = meta.bpm or _first_id3(id3, "TBPM")
        meta.key = meta.key or _first_id3(id3, "TKEY")
        meta.track = meta.track or _first_id3(id3, "TRCK")
        meta.isrc = meta.isrc or _first_id3(id3, "TSRC")
        meta.composer = meta.composer or _first_id3(id3, "TCOM")
        meta.copyright = meta.copyright or _first_id3(id3, "TCOP")
        meta.encoder = meta.encoder or _first_id3(id3, "TENC")
        comms = id3.getall("COMM")
        if comms and not meta.comment:
            meta.comment = _text(comms[0])
        woaf = id3.getall("WOAF")
        if woaf and not meta.url:
            meta.url = getattr(woaf[0], "url", "") or ""
        for apic in id3.getall("APIC"):
            if getattr(apic, "data", None):
                meta.cover_bytes = bytes(apic.data)
                meta.cover_mime = str(getattr(apic, "mime", "") or "image/jpeg")
                break
        for txxx in id3.getall("TXXX"):
            desc = str(getattr(txxx, "desc", "") or "TXXX")
            meta.extras[desc] = _text(txxx)
        for geob in id3.getall("GEOB"):
            desc = str(getattr(geob, "desc", "") or "GEOB")
            data = bytes(getattr(geob, "data", b"") or b"")
            if data:
                meta.geob.append((desc, data))
        for priv in id3.getall("PRIV"):
            owner = str(getattr(priv, "owner", "") or "PRIV")
            data = bytes(getattr(priv, "data", b"") or b"")
            if data:
                meta.priv.append((owner, data))

    if not meta.cover_bytes:
        try:
            mp4 = MP4(path)
            tags = mp4.tags or {}

            def atom(*keys: str) -> str:
                for key in keys:
                    values = tags.get(key)
                    if not values:
                        continue
                    item = values[0]
                    if isinstance(item, MP4FreeForm):
                        return bytes(item).decode("utf-8", errors="replace").strip()
                    return str(item).strip()
                return ""

            meta.artist = meta.artist or atom("\xa9ART")
            meta.albumartist = meta.albumartist or atom("aART") or meta.artist
            meta.album = meta.album or atom("\xa9alb")
            meta.title = meta.title or atom("\xa9nam")
            meta.genre = meta.genre or atom("\xa9gen")
            meta.date = meta.date or atom("\xa9day")
            meta.comment = meta.comment or atom("\xa9cmt")
            meta.grouping = meta.grouping or atom("\xa9grp")
            meta.label = (
                meta.label
                or atom("----:com.apple.iTunes:LABEL")
                or atom("----:com.apple.iTunes:publisher")
                or meta.grouping
            )
            meta.key = meta.key or atom(
                "----:com.apple.iTunes:initialkey",
                "----:com.apple.iTunes:KEY",
            )
            meta.isrc = meta.isrc or atom("----:com.apple.iTunes:ISRC")
            if not meta.bpm:
                tempo = tags.get("tmpo")
                if tempo:
                    meta.bpm = str(int(tempo[0]))
            covers = tags.get("covr") or []
            if covers:
                cover = covers[0]
                meta.cover_bytes = bytes(cover)
                fmt = int(getattr(cover, "imageformat", 0) or 0)
                meta.cover_mime = "image/png" if fmt == int(MP4Cover.FORMAT_PNG) else "image/jpeg"
        except Exception:
            pass
    return meta


def read_dest_fields(path: Path) -> dict[str, Any]:
    """What Traktor/Rekordbox would see on a generated M4A."""
    out: dict[str, Any] = {
        "artist": "",
        "albumartist": "",
        "album": "",
        "title": "",
        "label": "",
        "grouping": "",
        "genre": "",
        "date": "",
        "bpm": "",
        "key": "",
        "track": "",
        "isrc": "",
        "comment": "",
        "cover": False,
        "has_stem_atom": False,
    }
    try:
        mp4 = MP4(path)
    except Exception:
        return out
    tags = mp4.tags or {}

    def atom(*keys: str) -> str:
        for key in keys:
            values = tags.get(key)
            if not values:
                continue
            item = values[0]
            if isinstance(item, MP4FreeForm):
                return bytes(item).decode("utf-8", errors="replace").strip()
            return str(item).strip()
        return ""

    out["title"] = atom("\xa9nam")
    out["artist"] = atom("\xa9ART")
    out["albumartist"] = atom("aART")
    out["album"] = atom("\xa9alb")
    out["genre"] = atom("\xa9gen")
    out["date"] = atom("\xa9day")
    out["comment"] = atom("\xa9cmt")
    out["grouping"] = atom("\xa9grp")
    out["label"] = atom("----:com.apple.iTunes:LABEL") or out["grouping"]
    out["key"] = atom(
        "----:com.apple.iTunes:initialkey",
        "----:com.apple.iTunes:KEY",
    )
    out["isrc"] = atom("----:com.apple.iTunes:ISRC")
    tempo = tags.get("tmpo")
    if tempo:
        out["bpm"] = str(int(tempo[0]))
    trkn = tags.get("trkn")
    if trkn:
        out["track"] = str(trkn[0][0])
    out["cover"] = bool(tags.get("covr"))
    out["has_stem_atom"] = _has_stem_atom(path) if is_stem_container(path) else True
    return out


def _has_stem_atom(path: Path) -> bool:
    try:
        completed = subprocess.run(
            [_mp4box(), "-info", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception:
        return False
    text = (completed.stdout or "") + (completed.stderr or "")
    return "stem:" in text.lower() or "\tstem:" in text


def _tracknum(value: str) -> str:
    text = (value or "").split("/")[0].strip()
    return text if text.isdigit() else ""


def _tempo(value: str) -> str:
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return ""


def _itags_file(meta: SourceMeta, *, title: str, cover: Path | None) -> str:
    lines = [
        f"name={title}" if title else "",
        f"artist={meta.artist}" if meta.artist else "",
        f"album={meta.album}" if meta.album else "",
        f"album_artist={meta.albumartist or meta.artist}"
        if (meta.albumartist or meta.artist)
        else "",
        f"group={meta.grouping or meta.label}" if (meta.grouping or meta.label) else "",
        f"genre={meta.genre}" if meta.genre else "",
        f"created={meta.date}" if meta.date else "",
        f"comment={meta.comment.replace(chr(10), ' ')}" if meta.comment else "",
        f"composer={meta.composer}" if meta.composer else "",
        f"copyright={meta.copyright}" if meta.copyright else "",
        f"tracknum={_tracknum(meta.track)}" if _tracknum(meta.track) else "",
        f"tempo={_tempo(meta.bpm)}" if _tempo(meta.bpm) else "",
        f"cover={cover}" if cover is not None else "",
        "tool=stems",
        f"cust=com.apple.iTunes,LABEL,{meta.label}" if meta.label else "",
        f"cust=com.apple.iTunes,initialkey,{meta.key}" if meta.key else "",
        f"cust=com.apple.iTunes,ISRC,{meta.isrc}" if meta.isrc else "",
    ]
    for desc, value in meta.extras.items():
        safe = desc.replace(",", " ").replace("\n", " ")[:80]
        val = value.replace("\n", " ")
        if safe and val:
            lines.append(f"cust=com.apple.iTunes,{safe},{val}")
    return "\n".join(line for line in lines if line) + "\n"


def _cover_temp(meta: SourceMeta, folder: Path) -> Path | None:
    if not meta.cover_bytes:
        return None
    suffix = ".png" if "png" in (meta.cover_mime or "").lower() else ".jpg"
    path = folder / f"cover{suffix}"
    path.write_bytes(meta.cover_bytes)
    return path


def _apply_mp4box(dest: Path, meta: SourceMeta, *, title: str) -> None:
    with tempfile.TemporaryDirectory(prefix="stems-tags-") as tmp:
        tmp_path = Path(tmp)
        cover = _cover_temp(meta, tmp_path)
        tags_file = tmp_path / "itags.txt"
        tags_file.write_text(_itags_file(meta, title=title, cover=cover), encoding="utf-8")
        completed = subprocess.run(
            [_mp4box(), "-itags", str(tags_file), "-quiet", str(dest)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            err = (completed.stderr or completed.stdout or "").strip()
            raise MetaError(f"MP4Box -itags failed ({completed.returncode}): {err}")


def _cover_format(meta: SourceMeta) -> int:
    if "png" in (meta.cover_mime or "").lower() or meta.cover_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return int(MP4Cover.FORMAT_PNG)
    return int(MP4Cover.FORMAT_JPEG)


def _freeform(value: str) -> MP4FreeForm:
    return MP4FreeForm(value.encode("utf-8"))


def _apply_mutagen_pair(dest: Path, meta: SourceMeta, *, title: str) -> None:
    """Vocals/instrumental M4A: mutagen is safe and is what Traktor reads for covr."""
    mp4 = MP4(dest)
    if mp4.tags is None:
        mp4.add_tags()
    tags = mp4.tags
    assert tags is not None
    if title:
        tags["\xa9nam"] = [title]
    if meta.artist:
        tags["\xa9ART"] = [meta.artist]
    if meta.albumartist or meta.artist:
        tags["aART"] = [meta.albumartist or meta.artist]
    if meta.album:
        tags["\xa9alb"] = [meta.album]
    if meta.genre:
        tags["\xa9gen"] = [meta.genre]
    if meta.date:
        tags["\xa9day"] = [meta.date]
    if meta.comment:
        tags["\xa9cmt"] = [meta.comment.replace("\n", " ")]
    grouping = meta.grouping or meta.label
    if grouping:
        tags["\xa9grp"] = [grouping]
    if meta.composer:
        tags["\xa9wrt"] = [meta.composer]
    tempo = _tempo(meta.bpm)
    if tempo:
        tags["tmpo"] = [int(tempo)]
    track = _tracknum(meta.track)
    if track:
        tags["trkn"] = [(int(track), 0)]
    if meta.label:
        tags["----:com.apple.iTunes:LABEL"] = [_freeform(meta.label)]
        tags["----:com.apple.iTunes:publisher"] = [_freeform(meta.label)]
    if meta.key:
        tags["----:com.apple.iTunes:initialkey"] = [_freeform(meta.key)]
        tags["----:com.apple.iTunes:KEY"] = [_freeform(meta.key)]
    if meta.isrc:
        tags["----:com.apple.iTunes:ISRC"] = [_freeform(meta.isrc)]
    if meta.cover_bytes:
        tags["covr"] = [MP4Cover(meta.cover_bytes, imageformat=_cover_format(meta))]
    for desc, value in meta.extras.items():
        safe = desc.replace("\n", " ")[:80]
        if safe and value:
            tags[f"----:com.apple.iTunes:{safe}"] = [_freeform(value.replace("\n", " "))]
    for desc, data in meta.geob:
        tags[f"----:com.apple.iTunes:GEOB:{desc[:60]}"] = [MP4FreeForm(data)]
    for owner, data in meta.priv:
        tags[f"----:com.apple.iTunes:PRIV:{owner[:60]}"] = [MP4FreeForm(data)]
    mp4.save()


def copy_source_tags(
    source: Path,
    dest: Path,
    *,
    title_suffix: str | None = None,
) -> dict[str, Any]:
    """Copy source metadata onto ``dest``. STEM files use MP4Box, not mutagen."""
    dest = Path(dest)
    if not dest.is_file():
        raise MetaError(f"cannot tag missing file: {dest}")
    meta = read_source_meta(source)
    title = meta.titled(title_suffix)
    if is_stem_container(dest):
        _apply_mp4box(dest, meta, title=title)
    else:
        _apply_mutagen_pair(dest, meta, title=title)
    written = {
        "source": str(source),
        "dest": str(dest),
        "artist": meta.artist,
        "title": title,
        "album": meta.album,
        "label": meta.label,
        "bpm": meta.bpm,
        "key": meta.key,
        "cover": bool(meta.cover_bytes),
        "cues": len(meta.geob) + len(meta.priv),
        "stem_atom_kept": _has_stem_atom(dest) if is_stem_container(dest) else None,
    }
    return written


def compare_tags(
    source: Path,
    dest: Path,
    *,
    title_suffix: str | None = None,
) -> list[str]:
    """Return mismatch strings. Empty list means dest carries the source fields."""
    if not dest.is_file():
        return [f"missing {dest.name}"]
    src = read_source_meta(source)
    got = read_dest_fields(dest)
    expected_title = src.titled(title_suffix)
    issues: list[str] = []

    def check(field: str, want: str, have: str) -> None:
        if not want:
            return
        if have.casefold() != want.casefold():
            issues.append(f"{field}: want {want!r} got {have!r}")

    check("artist", src.artist, got["artist"])
    check("albumartist", src.albumartist, got["albumartist"])
    check("album", src.album, got["album"])
    check("title", expected_title, got["title"])
    check("label", src.label, got["label"])
    check("comment", " ".join(src.comment.split()), " ".join(got["comment"].split()))
    check("genre", src.genre, got["genre"])
    check("date", src.date, got["date"])
    if src.bpm and _tempo(src.bpm) != _tempo(got["bpm"]):
        issues.append(f"bpm: want {src.bpm!r} got {got['bpm']!r}")
    if src.key and got["key"] and src.key.casefold() != got["key"].casefold():
        issues.append(f"key: want {src.key!r} got {got['key']!r}")
    elif src.key and not got["key"]:
        issues.append(f"key: want {src.key!r} got missing")
    if src.cover_bytes and not got["cover"]:
        issues.append("cover: source has artwork, dest does not")
    if is_stem_container(dest) and not got["has_stem_atom"]:
        issues.append("stem udta atom missing (Traktor will not see four decks)")
    return issues
