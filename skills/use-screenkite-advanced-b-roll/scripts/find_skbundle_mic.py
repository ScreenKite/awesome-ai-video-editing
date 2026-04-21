#!/usr/bin/env python3
"""Locate the microphone audio file inside a ScreenKite .skbundle.

Usage:
    uv run find_skbundle_mic.py <bundle_path>
    uv run find_skbundle_mic.py <bundle_path> --json
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def find_mic(bundle: Path) -> Path | None:
    """Return the first microphone_*.m4a inside <bundle>/media/, or None."""
    media = bundle / "media"
    if not media.is_dir():
        return None
    for p in sorted(media.glob("microphone_*.m4a")):
        return p
    # Fallback: any microphone_*.* file
    for p in sorted(media.glob("microphone_*")):
        if p.suffix.lower() in (".m4a", ".wav", ".mp3", ".aac"):
            return p
    return None


def list_media(bundle: Path) -> dict[str, list[str]]:
    media = bundle / "media"
    out: dict[str, list[str]] = {"screen": [], "camera": [], "microphone": [], "system_audio": [], "other": []}
    if not media.is_dir():
        return out
    for p in sorted(media.iterdir()):
        if not p.is_file():
            continue
        name = p.name
        if name.startswith("screen_"):
            out["screen"].append(str(p))
        elif name.startswith("camera_"):
            out["camera"].append(str(p))
        elif name.startswith("microphone_"):
            out["microphone"].append(str(p))
        elif name.startswith("system_audio_"):
            out["system_audio"].append(str(p))
        else:
            out["other"].append(str(p))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true", help="List all media files, not just mic")
    args = ap.parse_args()

    bundle = args.bundle.resolve()
    if not bundle.is_dir() or not bundle.suffix == ".skbundle":
        sys.exit(f"Not a .skbundle directory: {bundle}")

    if args.all:
        data = list_media(bundle)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            for k, v in data.items():
                for p in v:
                    print(f"{k:15s} {p}")
        return

    mic = find_mic(bundle)
    if mic is None:
        sys.exit(f"No microphone_*.m4a found in {bundle}/media/")
    if args.json:
        print(json.dumps({"mic": str(mic)}))
    else:
        print(mic)


if __name__ == "__main__":
    main()
