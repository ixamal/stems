"""Python tools for NUO-STEMS extract, catalog, and related audio jobs.

Ported from https://github.com/davidrichardnelson/music into OOP modules.
Audio stays on disk. This package never writes collection.nml or master.db.

Import tools from their modules, e.g. ``from py.extract_stems import StemExtractor``.
Eager imports here would break ``python3 -m py.extract_stems``.
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
    "__version__",
]


def __getattr__(name: str):
    if name == "AppleFriendly":
        from py.apple_friendly import AppleFriendly

        return AppleFriendly
    if name == "SimpleMp3":
        from py.simple_mp3 import SimpleMp3

        return SimpleMp3
    if name == "StemCatalog":
        from py.catalog import StemCatalog

        return StemCatalog
    if name == "StemExtractor":
        from py.extract_stems import StemExtractor

        return StemExtractor
    if name == "TagUpdater":
        from py.tag_updater import TagUpdater

        return TagUpdater
    if name == "TrakExtractor":
        from py.trak_extract import TrakExtractor

        return TrakExtractor
    if name == "NumberedDupeCleanup":
        from py.cleanup_numbered import NumberedDupeCleanup

        return NumberedDupeCleanup
    if name == "UnknownRoleCleanup":
        from py.cleanup_unknown import UnknownRoleCleanup

        return UnknownRoleCleanup
    if name == "VocalsInstrumental":
        from py.vocals_instrumental import VocalsInstrumental

        return VocalsInstrumental
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
