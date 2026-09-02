"""stems ``py/`` — generate, extract, and catalog DJ stems.

Built for a 35k+ library that a GUI cannot batch. File shapes and the
``mel_vocals_bs_others`` split follow NUO-STEMS (Alex / DJ NUO,
https://nuo-stems.com); this package is the unattended CLI.

Layout
------
* ``py.exec`` — stem factory (Mel pair, BS-RoFormer ``.stem.m4a``, extract, cleanup)
* ``py.utils`` — paths, ffmpeg, catalog, Apple Music guard, NI stream map
* ``py.tools`` — headset MP3, filename tags, ``.trak`` unpack

Audio stays on disk under ``~/Music/stems_audio``. This package never writes
``collection.nml`` or Rekordbox ``master.db``. It refuses Apple Music's
``Media.localized`` tree. Every CLI writes ``log/`` (``.log``, JSON, charts)
unless ``--quiet``. ``--execute`` opens an Aqua progress window until Close
and mails the local notify address.

    python3 -m py
    .venv/bin/python -m py.exec.separate --path m3u/nuo_queue_test4.m3u

Ported in part from https://github.com/davidrichardnelson/music.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = [
    "AppleFriendly",
    "SimpleMp3",
    "StemCatalog",
    "StemExtractor",
    "TagUpdater",
    "TrakExtractor",
    "NumberedDupeCleanup",
    "UnknownRoleCleanup",
    "VocalsInstrumental",
    "LocalSeparator",
    "MetaValidator",
    "__version__",
]


def __getattr__(name: str):
    if name == "AppleFriendly":
        from py.utils.apple import AppleFriendly

        return AppleFriendly
    if name == "SimpleMp3":
        from py.tools.simple_mp3 import SimpleMp3

        return SimpleMp3
    if name == "StemCatalog":
        from py.utils.catalog import StemCatalog

        return StemCatalog
    if name == "StemExtractor":
        from py.exec.extract_stems import StemExtractor

        return StemExtractor
    if name == "TagUpdater":
        from py.tools.tag_updater import TagUpdater

        return TagUpdater
    if name == "TrakExtractor":
        from py.tools.trak_extract import TrakExtractor

        return TrakExtractor
    if name == "NumberedDupeCleanup":
        from py.exec.cleanup_numbered import NumberedDupeCleanup

        return NumberedDupeCleanup
    if name == "UnknownRoleCleanup":
        from py.exec.cleanup_unknown import UnknownRoleCleanup

        return UnknownRoleCleanup
    if name == "VocalsInstrumental":
        from py.exec.vocals_instrumental import VocalsInstrumental

        return VocalsInstrumental
    if name == "LocalSeparator":
        from py.exec.separate import LocalSeparator

        return LocalSeparator
    if name == "MetaValidator":
        from py.exec.validate_meta import MetaValidator

        return MetaValidator
    raise AttributeError(f"module 'py' has no attribute {name!r}")
