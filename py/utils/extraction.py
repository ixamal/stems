"""py.utils.extraction — NI STEM stream map and pair naming.

Native Instruments STEM containers hold five audio streams:

* ``0`` mix / master
* ``1`` drums
* ``2`` bass
* ``3`` other (highs / melody — not “instrumental” by itself)
* ``4`` vocals / acapella

Rekordbox does not play the container. The DJ pair is:

* **vocals** = stream 4 (AAC copy)
* **instrumental** = streams 1+2+3 mixed (never stream 3 alone)

Re-exports the path helpers extract tools share so callers have one import.
"""

from __future__ import annotations

from py.utils.paths import (  # noqa: F401
    PAIR_ROLES,
    STEM_ROLES,
    container_basename,
    is_stem_container,
    sibling_stem,
)

__all__ = [
    "PAIR_ROLES",
    "STEM_ROLES",
    "container_basename",
    "is_stem_container",
    "sibling_stem",
]
