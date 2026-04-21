#!/usr/bin/env python3
"""Apply a cuts.json file to the currently open ScreenKite project.

Reads [{start, end, gap_s}, ...] from a cuts JSON file and calls
  /usr/local/bin/screenkite agent tool call --name editTimeline
with action=cut and the corresponding ranges.

Usage:
    python3 apply_cuts.py <cuts.json>
    python3 apply_cuts.py <cuts.json> --dry-run   # print what would be sent
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

SCREENKITE = "/usr/local/bin/screenkite"


def build_tool_input(cuts: list[dict]) -> dict:
    ranges = [{"start": c["start"], "end": c["end"]} for c in cuts]
    return {"action": "cut", "parameters": {"ranges": ranges}}


def call_screenkite(tool_input: dict) -> dict:
    result = subprocess.run(
        [
            SCREENKITE, "agent", "tool", "call",
            "--name", "editTimeline",
            "--input-json", json.dumps(tool_input),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(f"screenkite exited {result.returncode}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # Some versions emit plain text on success
        print(result.stdout)
        return {}


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply silence cuts to ScreenKite timeline")
    ap.add_argument("cuts_json", type=Path, help="Path to cuts.json produced by compute_silence_cuts.py")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the tool-input JSON that would be sent, then exit")
    args = ap.parse_args()

    if not args.cuts_json.exists():
        sys.exit(f"cuts file not found: {args.cuts_json}")

    cuts = json.loads(args.cuts_json.read_text())
    if not cuts:
        sys.exit("cuts.json is empty — nothing to apply")

    tool_input = build_tool_input(cuts)
    total_s = sum(c.get("gap_s", 0) for c in cuts)

    if args.dry_run:
        print(f"Would apply {len(cuts)} cuts ({total_s:.1f}s total):")
        print(json.dumps(tool_input, indent=2))
        return

    print(f"Applying {len(cuts)} cuts ({total_s:.1f}s total)…")
    response = call_screenkite(tool_input)

    if response:
        print(json.dumps(response, indent=2))
    print(f"Done. To undo a cut: screenkite agent tool call --name editTimeline --input-json '{{\"action\":\"undo\"}}' --json")


if __name__ == "__main__":
    main()
