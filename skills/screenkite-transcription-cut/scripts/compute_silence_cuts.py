#!/usr/bin/env python3
"""Compute silence-based cut ranges from a Scribe word-level JSON transcript.

Reads the word/spacing entries produced by ElevenLabs Scribe and emits time
ranges that are silent for at least --min-silence seconds. Each range is
inset by --pad seconds on both sides so surrounding words are not clipped.

Outputs (pick one):
  --output <path>        Write [{start, end, gap_s}, ...] JSON to file.
  --emit-tool-input      Print ScreenKite editTimeline tool-input JSON to stdout.
  --dry-run              Print a human-readable table to stdout, no file written.

Usage:
    python3 compute_silence_cuts.py transcript.json --min-silence 0.8 --pad 0.15
    python3 compute_silence_cuts.py transcript.json --dry-run
    python3 compute_silence_cuts.py transcript.json --emit-tool-input
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def compute_gaps(words: list[dict], min_silence: float) -> list[dict]:
    """Return list of {gap_start, gap_end, gap_s} for gaps >= min_silence."""
    gaps: list[dict] = []
    prev_end: float | None = None

    for w in words:
        wtype = w.get("type", "word")
        start = w.get("start")
        end = w.get("end")

        if start is None:
            continue

        # spacing entries are explicit silences; word/audio_event entries have
        # their own start/end. Either way, measure gap from previous word end.
        if prev_end is not None:
            gap = start - prev_end
            if gap >= min_silence:
                gaps.append({
                    "gap_start": prev_end,
                    "gap_end": start,
                    "gap_s": round(gap, 3),
                })

        if wtype == "spacing":
            # spacing entries represent silence; their end IS the silence end
            if end is not None and prev_end is not None:
                inner_gap = end - start
                if inner_gap >= min_silence:
                    gaps.append({
                        "gap_start": start,
                        "gap_end": end,
                        "gap_s": round(inner_gap, 3),
                    })
                prev_end = end
            # don't update prev_end from spacing if end is missing
        else:
            prev_end = end if end is not None else start

    return gaps


def gaps_to_cuts(gaps: list[dict], pad: float) -> list[dict]:
    """Convert raw gaps to padded cut ranges, deduplicated and sorted."""
    cuts: list[dict] = []
    for g in gaps:
        start = round(g["gap_start"] + pad, 3)
        end = round(g["gap_end"] - pad, 3)
        if end <= start:
            continue  # gap too short after padding
        cuts.append({"start": start, "end": end, "gap_s": g["gap_s"]})
    # merge overlapping (shouldn't happen but defensive)
    cuts.sort(key=lambda c: c["start"])
    merged: list[dict] = []
    for c in cuts:
        if merged and c["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], c["end"])
            merged[-1]["gap_s"] = round(merged[-1]["gap_s"] + c["gap_s"], 3)
        else:
            merged.append(dict(c))
    return merged


def load_words(transcript_path: Path) -> list[dict]:
    data = json.loads(transcript_path.read_text())
    words = data.get("words", [])
    if not words:
        sys.exit(f"No 'words' array in {transcript_path}")
    return words


def print_dry_run(cuts: list[dict]) -> None:
    total_s = sum(c["gap_s"] for c in cuts)
    print(f"Silence cuts: {len(cuts)}  |  total removed: {total_s:.1f}s\n")
    print(f"{'#':>3}  {'start':>8}  {'end':>8}  {'gap':>6}")
    print("-" * 32)
    for i, c in enumerate(cuts, 1):
        print(f"{i:>3}  {c['start']:>8.3f}  {c['end']:>8.3f}  {c['gap_s']:>5.2f}s")


def emit_tool_input(cuts: list[dict]) -> None:
    ranges = [{"start": c["start"], "end": c["end"]} for c in cuts]
    payload = {"action": "cut", "parameters": {"ranges": ranges}}
    print(json.dumps(payload))


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute silence cut ranges from Scribe JSON")
    ap.add_argument("transcript", type=Path, help="Path to Scribe word-level JSON")
    ap.add_argument("--min-silence", type=float, default=0.8,
                    help="Minimum silence duration to cut (seconds, default 0.8)")
    ap.add_argument("--pad", type=float, default=0.15,
                    help="Padding to keep at each cut edge (seconds, default 0.15)")
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

    words = load_words(args.transcript)
    gaps = compute_gaps(words, args.min_silence)
    cuts = gaps_to_cuts(gaps, args.pad)

    if not cuts:
        print(f"No silences >= {args.min_silence}s found. Nothing to cut.", file=sys.stderr)
        if args.emit_tool_input:
            # emit a no-op so CLI callers don't fail
            print(json.dumps({"action": "cut", "parameters": {"ranges": []}}))
        sys.exit(0)

    if args.dry_run:
        print_dry_run(cuts)
    elif args.emit_tool_input:
        emit_tool_input(cuts)
    else:
        out_path = args.output or (args.transcript.parent.parent / "cuts.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(cuts, indent=2))
        total_s = sum(c["gap_s"] for c in cuts)
        print(f"Wrote {len(cuts)} cuts ({total_s:.1f}s total) → {out_path}")


if __name__ == "__main__":
    main()
