"""``python3 -m py`` — list the OOP tools."""

from __future__ import annotations

from py import __version__

COMMANDS = [
    ("py.exec.separate", "Mel vocals/instrumental + BS-RoFormer .stem.m4a"),
    ("py.exec.extract_stems", "NI STEM → drums / bass / other / acapella"),
    ("py.exec.vocals_instrumental", "Pair from STEM, or queue paths into m3u/"),
    ("py.exec.cleanup_unknown", "Quarantine nameless bass/drums/other/vocals WAVs"),
    ("py.exec.validate_meta", "QA: generated files must carry source artist/label/BPM/cover"),
    ("py.utils.apple", "H.264/AAC or AAC M4A — never writes Music.app"),
    ("py.tools.simple_mp3", "320k MP3 convert or collect (H2O headset)"),
    ("py.tools.tag_updater", "Artist / title from 'Artist - Title' filenames"),
    ("py.tools.trak_extract", "Unpack .trak archives + M3U"),
]


def main() -> None:
    print(f"stems py {__version__} — run from repo root:\n")
    for mod, desc in COMMANDS:
        print(f"  python3 -m {mod} --help")
        print(f"      {desc}\n")
    print("Dry-run is the default. Pass --execute to write.")
    print("Verbose log/ JSON + charts are the default. Pass --quiet to skip.")
    print("--execute opens an Aqua progress window until Close, and mails david@alkalurops.org. --no-gui / --no-notify skip.")
    print("Deps: pip install -r py/exec/requirements.txt  (root requirements.txt includes that).")
    print("35k+ crate: this CLI is the generator. NUO-STEMS (Alex / DJ NUO) is the licensed reference, not a batch tool.")
    print("Library remaps stay in music_migration. This package does not touch NML or master.db.")


if __name__ == "__main__":
    main()
