#!/usr/bin/env python3
"""Pack Scribe transcripts into a phrase-level markdown view.

Groups word-level entries into phrases, breaking on silence >= threshold OR
speaker change. Each phrase gets [start-end] prefix for addressing cuts.
Output: <edit-dir>/takes_packed.md

Usage:
    python3 pack_transcripts.py --edit-dir <edit_dir>
    python3 pack_transcripts.py --edit-dir <edit_dir> --silence-threshold 0.5
    python3 pack_transcripts.py --edit-dir <edit_dir> -o out.md
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def format_time(seconds: float) -> str:
    return f"{seconds:06.2f}"


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m}m {s:04.1f}s"


def group_into_phrases(words: list[dict], silence_threshold: float) -> list[dict]:
    phrases: list[dict] = []
    current_words: list[dict] = []
    current_start: float | None = None
    current_speaker: str | None = None

    def flush() -> None:
        nonlocal current_words, current_start, current_speaker
        if not current_words:
            return
        parts: list[str] = []
        for w in current_words:
            t = w.get("type", "word")
            raw = (w.get("text") or "").strip()
            if not raw:
                continue
            if t == "audio_event" and not raw.startswith("("):
                raw = f"({raw})"
            parts.append(raw)
        if not parts:
            current_words = []
            current_start = None
            current_speaker = None
            return
        text = " ".join(parts)
        for a, b in ((" ,", ","), (" .", "."), (" ?", "?"), (" !", "!")):
            text = text.replace(a, b)
        end_time = current_words[-1].get("end", current_words[-1].get("start", current_start or 0.0))
        phrases.append({
            "start": current_start,
            "end": end_time,
            "text": text,
            "speaker_id": current_speaker,
        })
        current_words = []
        current_start = None
        current_speaker = None

    prev_end: float | None = None

    for w in words:
        t = w.get("type", "word")
        if t == "spacing":
            start = w.get("start")
            end = w.get("end")
            if start is not None and end is not None and (end - start) >= silence_threshold:
                flush()
            continue
        start = w.get("start")
        if start is None:
            continue
        speaker = w.get("speaker_id")
        if current_speaker is not None and speaker is not None and speaker != current_speaker:
            flush()
        if prev_end is not None and start - prev_end >= silence_threshold:
            flush()
        if current_start is None:
            current_start = start
            current_speaker = speaker
        current_words.append(w)
        prev_end = w.get("end", start)

    flush()
    return phrases


def pack_one_file(json_path: Path, silence_threshold: float) -> tuple[str, float, list[dict]]:
    data = json.loads(json_path.read_text())
    words = data.get("words", [])
    phrases = group_into_phrases(words, silence_threshold)
    if phrases:
        duration = phrases[-1]["end"] - phrases[0]["start"]
    else:
        duration = 0.0
    return json_path.stem, duration, phrases


def render_markdown(
    entries: list[tuple[str, float, list[dict]]],
    silence_threshold: float,
) -> str:
    lines: list[str] = []
    lines.append("# Packed transcripts")
    lines.append("")
    lines.append(f"Phrase-level, grouped on silences >= {silence_threshold:.1f}s or speaker change.")
    lines.append("Use `[start-end]` ranges to address cuts in the plan.")
    lines.append("")
    for name, duration, phrases in entries:
        lines.append(f"## {name}  (duration: {format_duration(duration)}, {len(phrases)} phrases)")
        if not phrases:
            lines.append("  _no speech detected_")
            lines.append("")
            continue
        for p in phrases:
            spk = p.get("speaker_id")
            if spk is not None:
                spk_str = str(spk)
                if spk_str.startswith("speaker_"):
                    spk_str = spk_str[len("speaker_"):]
                spk_tag = f" S{spk_str}"
            else:
                spk_tag = ""
            lines.append(f"  [{format_time(p['start'])}-{format_time(p['end'])}]{spk_tag} {p['text']}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edit-dir", type=Path, required=True)
    ap.add_argument("--silence-threshold", type=float, default=0.5)
    ap.add_argument("-o", "--output", type=Path, default=None)
    args = ap.parse_args()

    edit_dir = args.edit_dir.resolve()
    transcripts_dir = edit_dir / "transcripts"
    if not transcripts_dir.is_dir():
        sys.exit(f"no transcripts directory at {transcripts_dir}")

    json_files = sorted(transcripts_dir.glob("*.json"))
    if not json_files:
        sys.exit(f"no .json files in {transcripts_dir}")

    entries = [pack_one_file(p, args.silence_threshold) for p in json_files]
    markdown = render_markdown(entries, args.silence_threshold)

    out_path = args.output or (edit_dir / "takes_packed.md")
    out_path.write_text(markdown)

    total_phrases = sum(len(e[2]) for e in entries)
    total_duration = sum(e[1] for e in entries)
    kb = out_path.stat().st_size / 1024
    print(f"packed {len(entries)} transcripts -> {out_path}")
    print(f"  {total_phrases} phrases, {format_duration(total_duration)} total runtime")
    print(f"  {kb:.1f} KB")


if __name__ == "__main__":
    main()
