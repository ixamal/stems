"""python3 -m py  →  list the OOP tools."""

from __future__ import annotations

from py import __version__  # lazy package; no tool-module import

COMMANDS = [
    ("py.extract_stems", "NI STEM → drums / bass / other / acapella under stems_audio"),
    ("py.simple_mp3", "320k MP3 convert or collect (H2O headset, not stems_audio)"),
    ("py.tag_updater", "Artist / title from 'Artist - Title' filenames"),
    ("py.trak_extract", "Unpack .trak archives + M3U"),
    ("py.apple_friendly", "H.264/AAC or AAC M4A — never writes Music.app"),
    ("py.cleanup_unknown", "Quarantine nameless bass/drums/other/vocals WAVs"),
    ("py.cleanup_numbered", "Trash Name (2).ext when original exists and sizes match"),
    ("py.vocals_instrumental", "Acapella + instrumental from STEM; else NUO queue"),
]


def main() -> None:
    print(f"stems py {__version__} — run from repo root:\n")
    for mod, desc in COMMANDS:
        print(f"  python3 -m {mod} --help")
        print(f"      {desc}\n")
    print("Dry-run is the default. Pass --execute to write.")
    print("Library remaps stay in music_migration. This package does not touch NML or master.db.")


if __name__ == "__main__":
    main()
