#!/usr/bin/env python3
"""Apply an all_cuts.json (or any cuts JSON) to the currently open ScreenKite project.

Reads [{start, end, ...}, ...] from a cuts JSON file and calls:
  /usr/local/bin/screenkite-alpha agent tool call --name editTimeline

Usage:
    python3 apply_cuts.py <cuts.json>
    python3 apply_cuts.py <cuts.json> --dry-run   # print what would be sent
    python3 apply_cuts.py <cuts.json> --cli /usr/local/bin/screenkite
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_CLI = "/usr/local/bin/screenkite-alpha"


def build_tool_input(cuts: list[dict]) -> dict:
    ranges = [{"start": c["start"], "end": c["end"]} for c in cuts]
    return {"action": "cut", "parameters": {"ranges": ranges}}


def call_screenkite(cli: str, tool_input: dict) -> dict:
    result = subprocess.run(
        [
            cli, "agent", "tool", "call",
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
        print(result.stdout)
        return {}


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply cuts JSON to ScreenKite timeline")
    ap.add_argument("cuts_json", type=Path, help="Path to cuts JSON (all_cuts.json or cuts.json)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the tool-input JSON that would be sent, then exit")
    ap.add_argument("--cli", type=str, default=DEFAULT_CLI,
                    help=f"Path to screenkite CLI (default: {DEFAULT_CLI})")
    args = ap.parse_args()

    if not args.cuts_json.exists():
        sys.exit(f"cuts file not found: {args.cuts_json}")

    cuts = json.loads(args.cuts_json.read_text())
    if not cuts:
        sys.exit("cuts file is empty — nothing to apply")

    tool_input = build_tool_input(cuts)
    silence = sum(1 for c in cuts if c.get("kind") == "silence")
    fillers = sum(1 for c in cuts if c.get("kind") == "filler")
    total_s = sum(c["end"] - c["start"] for c in cuts)
    kind_str = ""
    if silence or fillers:
        kind_str = f" ({silence} silence + {fillers} filler)"

    if args.dry_run:
        print(f"Would apply {len(cuts)} cuts{kind_str} ({total_s:.2f}s total):")
        print(json.dumps(tool_input, indent=2))
        return

    print(f"Applying {len(cuts)} cuts{kind_str} ({total_s:.2f}s total)…")
    response = call_screenkite(args.cli, tool_input)

    if response:
        print(json.dumps(response, indent=2))
    print(
        "\nTo undo a cut:\n"
        f"  {args.cli} agent tool call --name editTimeline "
        "--input-json '{\"action\":\"undo\"}' --json"
    )


if __name__ == "__main__":
    main()
