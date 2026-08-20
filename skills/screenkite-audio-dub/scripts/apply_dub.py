#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Mute the original microphone track and import a time-matched dub mix.

Uses ScreenKite:
  props        mute=true on the source mic track
  add          type=audio + createTrack {name, language} to place the mix

Always pass --project. Mutations require a fresh projectRevision from stat.

Usage:
    python3 apply_dub.py --project /path/to.skbundle --mix dub/mix.wav \\
        --mute-track-id mic-studio-display-microphone --language en
    python3 apply_dub.py ... --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sk_cli import DEFAULT_SK, project_revision, sk_call


def load_cues_meta(cues_json: Path | None) -> dict:
    if not cues_json:
        return {}
    return json.loads(cues_json.read_text())


def find_audio_tracks(stat: dict) -> list[dict]:
    tracks = (stat.get("timeline") or {}).get("tracks") or []
    return [t for t in tracks if t.get("kind") == "audio"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Mute original mic and add dubbed audio track")
    ap.add_argument("--project", required=True, help="Absolute .skbundle path")
    ap.add_argument("--mix", type=Path, required=True, help="Time-matched mix.wav from gen_dub.py")
    ap.add_argument("--mute-track-id", default=None,
                    help="Audio track to mute (default: cues.json source_track_id, else Microphone)")
    ap.add_argument("--cues", type=Path, default=None, help="Optional cues.json for track id / language")
    ap.add_argument("--language", default=None, help="BCP-47 tag for the new dub track (e.g. en, ja, pt-BR)")
    ap.add_argument("--track-name", default=None, help="Display name for the new dub track")
    ap.add_argument("--sk", default=DEFAULT_SK, help="Path to screenkite binary")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-mute", action="store_true", help="Import dub without muting the original mic")
    args = ap.parse_args()

    project = str(Path(args.project).resolve())
    mix = args.mix.resolve()
    if not mix.exists():
        sys.exit(f"mix not found: {mix}")

    meta = load_cues_meta(args.cues.resolve()) if args.cues else {}
    language = args.language or meta.get("target_language") or "en"
    track_name = args.track_name or f"Dub {language.upper()}"
    mute_id = args.mute_track_id or meta.get("source_track_id")

    stat = sk_call("stat", {"scope": "summary"}, project, sk=args.sk)
    audio_tracks = find_audio_tracks(stat)
    if mute_id is None:
        for t in audio_tracks:
            name = (t.get("displayName") or t.get("name") or "").lower()
            if "mic" in name or "microphone" in name:
                mute_id = t["id"]
                break
        if mute_id is None and audio_tracks:
            mute_id = audio_tracks[0]["id"]

    print("audio tracks:")
    for t in audio_tracks:
        mark = "  <- mute" if t.get("id") == mute_id else ""
        print(f"  {t.get('id')}  {t.get('displayName') or t.get('name')}{mark}")
    print(f"mute:       {mute_id}")
    print(f"add:        {mix}")
    print(f"new track:  {track_name}  language={language}")
    print(f"revision:   {stat.get('projectRevision')}")

    if args.dry_run:
        print("dry-run: no mutations")
        return

    if not args.skip_mute:
        if not mute_id:
            sys.exit("could not resolve a microphone track to mute; pass --mute-track-id")
        rev = project_revision(project, sk=args.sk)
        mute_res = sk_call(
            "props",
            {
                "trackId": mute_id,
                "expectedProjectRevision": rev,
                "properties": {"mute": True},
            },
            project,
            sk=args.sk,
        )
        print("muted:", json.dumps(mute_res, indent=2)[:800])

    rev = project_revision(project, sk=args.sk)
    duration = ((stat.get("project") or {}).get("duration")) or meta.get("timeline_duration")
    add_payload: dict = {
        "type": "audio",
        "source": str(mix),
        "time": 0,
        "createTrack": {"name": track_name, "language": language},
        "expectedProjectRevision": rev,
        "options": {"volume": 1.0, "description": f"Time-matched {language} dub"},
    }
    if duration:
        add_payload["options"]["end"] = float(duration)

    add_res = sk_call("add", add_payload, project, sk=args.sk)
    print("added:", json.dumps(add_res, indent=2)[:1200])

    after = sk_call("stat", {"scope": "summary"}, project, sk=args.sk)
    print("audio tracks after:")
    for t in find_audio_tracks(after):
        print(f"  {t.get('id')}  {t.get('displayName') or t.get('name')}")


if __name__ == "__main__":
    main()
