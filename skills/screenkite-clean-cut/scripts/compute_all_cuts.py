#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Compute merged silence + filler-word cut ranges from a Scribe transcript.

Reads the word-level JSON produced by ElevenLabs Scribe and builds a single
sorted, deduplicated list of cut ranges covering:
  1. Silence gaps >= --min-silence seconds (padded by --silence-pad)
  2. Filler words  (um, uh, ah, er, hmm, hm by default, padded by --filler-pad)

All ranges are merged before output so overlapping cuts (e.g. a filler that
falls inside a silence gap) are collapsed into one.

Outputs (pick one):
  --output <path>       Write [{start, end, kind, gap_s?}, ...] JSON to file.
  --emit-tool-input     Print ScreenKite editTimeline tool-input JSON to stdout.
  --dry-run             Print a human-readable table to stdout, no file written.

Usage:
    python3 compute_all_cuts.py transcript.json --dry-run
    python3 compute_all_cuts.py transcript.json \\
        --min-silence 0.8 --silence-pad 0.15 --filler-pad 0.03 --emit-tool-input
    python3 compute_all_cuts.py transcript.json --output all_cuts.json
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_FILLERS = {"um", "uh", "ah", "er", "hmm", "hm"}


# ---------------------------------------------------------------------------
# Silence gap detection (ported from compute_silence_cuts.py)
# ---------------------------------------------------------------------------

def compute_silence_gaps(words: list[dict], min_silence: float) -> list[dict]:
    """Return [{gap_start, gap_end, gap_s}] for gaps >= min_silence."""
    gaps: list[dict] = []
    prev_end: float | None = None

    for w in words:
        wtype = w.get("type", "word")
        start = w.get("start")
        end = w.get("end")

        if start is None:
            continue

        if prev_end is not None:
            gap = start - prev_end
            if gap >= min_silence:
                gaps.append({"gap_start": prev_end, "gap_end": start, "gap_s": round(gap, 3)})

        if wtype == "spacing":
            if end is not None and prev_end is not None:
                inner_gap = end - start
                if inner_gap >= min_silence:
                    gaps.append({"gap_start": start, "gap_end": end, "gap_s": round(inner_gap, 3)})
            if end is not None:
                prev_end = end
        else:
            prev_end = end if end is not None else start

    return gaps


def silence_gaps_to_cuts(gaps: list[dict], pad: float) -> list[dict]:
    cuts: list[dict] = []
    for g in gaps:
        start = round(g["gap_start"] + pad, 4)
        end = round(g["gap_end"] - pad, 4)
        if end <= start:
            continue
        cuts.append({"start": start, "end": end, "kind": "silence", "gap_s": g["gap_s"]})
    return cuts


# ---------------------------------------------------------------------------
# Filler-word detection
# ---------------------------------------------------------------------------

def compute_filler_cuts(words: list[dict], fillers: set[str], pad: float) -> list[dict]:
    """Return [{start, end, kind, text}] for each filler word hit."""
    cuts: list[dict] = []
    for w in words:
        if w.get("type", "word") != "word":
            continue
        clean = re.sub(r"[^a-z]", "", w["text"].lower())
        if clean in fillers:
            start = round(w["start"] - pad, 4)
            end = round(w["end"] + pad, 4)
            if end > start:
                cuts.append({
                    "start": max(start, 0.0),
                    "end": end,
                    "kind": "filler",
                    "text": w["text"].strip(),
                })
    return cuts


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

def merge_cuts(cuts: list[dict]) -> list[dict]:
    """Sort by start and merge overlapping ranges. Preserves kind/text of first."""
    if not cuts:
        return []
    cuts = sorted(cuts, key=lambda c: c["start"])
    merged: list[dict] = [dict(cuts[0])]
    for c in cuts[1:]:
        if c["start"] <= merged[-1]["end"]:
            # Overlap — extend end, accumulate gap_s if present
            merged[-1]["end"] = max(merged[-1]["end"], c["end"])
            if "gap_s" in c and "gap_s" in merged[-1]:
                merged[-1]["gap_s"] = round(merged[-1]["gap_s"] + c["gap_s"], 3)
        else:
            merged.append(dict(c))
    return merged


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def print_dry_run(silence_cuts: list[dict], filler_cuts: list[dict], merged: list[dict]) -> None:
    sil_total = sum(c["end"] - c["start"] for c in silence_cuts)
    fil_total = sum(c["end"] - c["start"] for c in filler_cuts)
    all_total = sum(c["end"] - c["start"] for c in merged)

    print(f"\n{'─'*52}")
    print(f"  SILENCE GAPS  ({len(silence_cuts)} cuts, ~{sil_total:.2f}s)")
    print(f"{'─'*52}")
    if silence_cuts:
        print(f"  {'#':<4} {'start':>8}  {'end':>8}  {'dur':>6}")
        print(f"  {'-'*36}")
        for i, c in enumerate(silence_cuts, 1):
            dur = c["end"] - c["start"]
            print(f"  {i:<4} {c['start']:>8.3f}  {c['end']:>8.3f}  {dur:>5.2f}s")
    else:
        print("  (none)")

    print(f"\n{'─'*52}")
    print(f"  FILLER WORDS  ({len(filler_cuts)} cuts, ~{fil_total:.2f}s)")
    print(f"{'─'*52}")
    if filler_cuts:
        print(f"  {'#':<4} {'word':<10} {'start':>8}  {'end':>8}")
        print(f"  {'-'*36}")
        for i, c in enumerate(filler_cuts, 1):
            print(f"  {i:<4} {c.get('text','?'):<10} {c['start']:>8.3f}  {c['end']:>8.3f}")
    else:
        print("  (none)")

    print(f"\n{'─'*52}")
    print(f"  COMBINED  {len(merged)} cuts  |  ~{all_total:.2f}s total removed")
    print(f"{'─'*52}\n")


def emit_tool_input(merged: list[dict]) -> None:
    ranges = [{"start": c["start"], "end": c["end"]} for c in merged]
    print(json.dumps({"action": "cut", "parameters": {"ranges": ranges}}))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compute merged silence + filler-word cuts from Scribe JSON"
    )
    ap.add_argument("transcript", type=Path, help="Path to Scribe word-level JSON")
    ap.add_argument(
        "--min-silence", type=float, default=0.8,
        help="Minimum silence gap to cut (seconds, default 0.8)",
    )
    ap.add_argument(
        "--silence-pad", type=float, default=0.15,
        help="Padding at each edge of a silence cut (seconds, default 0.15)",
    )
    ap.add_argument(
        "--filler-pad", type=float, default=0.03,
        help="Padding at each edge of a filler-word cut (seconds, default 0.03)",
    )
    ap.add_argument(
        "--fillers", type=str, default=None,
        help="Comma-separated list of filler words (default: um,uh,ah,er,hmm,hm)",
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--output", "-o", type=Path, default=None,
                      help="Write cuts JSON to this path")
    mode.add_argument("--emit-tool-input", action="store_true",
                      help="Print ScreenKite editTimeline input JSON to stdout")
    mode.add_argument("--dry-run", action="store_true",
                      help="Print human-readable table, no file written")
    args = ap.parse_args()

    if not args.transcript.exists():
        sys.exit(f"transcript not found: {args.transcript}")

    fillers = (
        {w.strip().lower() for w in args.fillers.split(",")}
        if args.fillers
        else DEFAULT_FILLERS
    )

    data = json.loads(args.transcript.read_text())
    words = data.get("words", [])
    if not words:
        sys.exit(f"No 'words' array in {args.transcript}")

    silence_gaps = compute_silence_gaps(words, args.min_silence)
    silence_cuts = silence_gaps_to_cuts(silence_gaps, args.silence_pad)
    filler_cuts = compute_filler_cuts(words, fillers, args.filler_pad)
    merged = merge_cuts(silence_cuts + filler_cuts)

    if not merged:
        print("No cuts found. Nothing to apply.", file=sys.stderr)
        if args.emit_tool_input:
            print(json.dumps({"action": "cut", "parameters": {"ranges": []}}))
        sys.exit(0)

    if args.dry_run:
        print_dry_run(silence_cuts, filler_cuts, merged)

    elif args.emit_tool_input:
        emit_tool_input(merged)

    else:
        out_path = args.output or (args.transcript.parent.parent / "all_cuts.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(merged, indent=2))
        total_s = sum(c["end"] - c["start"] for c in merged)
        print(
            f"Wrote {len(merged)} cuts ({total_s:.2f}s total: "
            f"{len(silence_cuts)} silence + {len(filler_cuts)} filler) → {out_path}"
        )


if __name__ == "__main__":
    main()
