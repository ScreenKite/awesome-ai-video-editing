#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Pack a word-level transcript (or SRT) into timed dub cues.

Accepts:
  - ScreenKite export-words JSON (schemaVersion 3, words[] in timeline seconds)
  - ElevenLabs Scribe JSON (words[] with type=word|spacing)
  - SRT subtitle file

Punctuation-only tokens are treated as gaps, not speech, so a long comma
that covers a pause becomes a phrase break instead of a 1.4s "cue".

Usage:
    python3 pack_cues.py transcript.json --duration 4.35
    python3 pack_cues.py transcript.json --srt-out source.srt --output cues.json
    python3 pack_cues.py source.srt --output cues.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PUNCT_RE = re.compile(r"^[\s.,!?;:，。！？、；：「」『』（）()\[\]…—\-–]+$")


def format_srt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def is_speech_token(text: str, token_type: str | None) -> bool:
    if token_type in ("spacing", "audio_event"):
        return False
    raw = (text or "").strip()
    if not raw:
        return False
    return PUNCT_RE.match(raw) is None


def load_words(path: Path) -> tuple[list[dict], dict]:
    """Return (speech words with start/end/text, meta)."""
    if path.suffix.lower() == ".srt":
        cues = parse_srt(path)
        words = [
            {"start": c["start"], "end": c["end"], "text": c["text"]}
            for c in cues
        ]
        meta = {
            "source_format": "srt",
            "timeline_duration": cues[-1]["end"] if cues else 0.0,
        }
        return words, meta

    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        sys.exit(f"unexpected JSON in {path}: expected object")

    raw_words = data.get("words") or []
    words: list[dict] = []
    for w in raw_words:
        start = w.get("start")
        end = w.get("end", start)
        if start is None:
            continue
        text = (w.get("text") or "").strip()
        if not text or w.get("type") in ("spacing", "audio_event"):
            continue
        words.append({
            "start": float(start),
            "end": float(end if end is not None else start),
            "text": text,
            "speech": is_speech_token(text, w.get("type")),
            "speaker_id": w.get("speaker_id"),
        })

    source = data.get("source") or {}
    meta = {
        "source_format": data.get("format") or "json",
        "provider": data.get("provider"),
        "timeline_duration": float(
            data.get("duration")
            or (words[-1]["end"] if words else 0.0)
        ),
        "source_track_id": source.get("trackId") or data.get("sourceTrackId"),
        "source_clip_id": source.get("clipId"),
        "source_text": data.get("text") or "",
        "language": data.get("language_code") or data.get("language"),
    }
    return words, meta


def parse_srt(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: list[dict] = []
    ts = re.compile(
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})"
    )

    def to_s(h, m, s, ms) -> float:
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0

    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        match = None
        body_start = 1
        for i, ln in enumerate(lines):
            match = ts.search(ln)
            if match:
                body_start = i + 1
                break
        if not match:
            continue
        start = to_s(*match.groups()[:4])
        end = to_s(*match.groups()[4:])
        body = " ".join(lines[body_start:]).strip()
        if body:
            cues.append({"start": start, "end": end, "text": body})
    return cues


def join_cue_text(tokens: list[dict]) -> str:
    parts: list[str] = []
    latin = any(ord(ch) < 128 and ch.isalpha() for w in tokens for ch in w["text"])
    for w in tokens:
        tok = w["text"]
        if latin and parts and tok[:1].isalnum() and parts[-1][-1:].isalnum():
            parts.append(" ")
        parts.append(tok)
    return "".join(parts).strip()


def group_cues(words: list[dict], silence_threshold: float) -> list[dict]:
    """Speech tokens form cues. Short punctuation sticks to the previous
    cue's text. Long punctuation (a pause tagged as a comma) breaks the cue
    without extending its end into the silence."""
    cues: list[dict] = []
    current: list[dict] = []

    def flush() -> None:
        speech = [w for w in current if w.get("speech", True)]
        if not speech:
            current.clear()
            return
        cues.append({
            "start": speech[0]["start"],
            "end": speech[-1]["end"],
            "text": join_cue_text(current),
            "speaker_id": speech[0].get("speaker_id"),
            "word_count": len(speech),
        })
        current.clear()

    prev_end: float | None = None
    prev_speaker = None
    for w in words:
        if not w.get("speech", True):
            if current:
                long_pause = (w["end"] - w["start"]) >= silence_threshold
                if not long_pause:
                    current.append(w)
                if long_pause:
                    flush()
                    prev_end = w["end"]
            elif prev_end is not None:
                prev_end = max(prev_end, w["end"])
            continue
        speaker = w.get("speaker_id")
        if current and speaker is not None and prev_speaker is not None and speaker != prev_speaker:
            flush()
        if prev_end is not None and w["start"] - prev_end >= silence_threshold:
            flush()
        current.append(w)
        prev_end = w["end"]
        prev_speaker = speaker
    flush()
    return cues


def render_srt(cues: list[dict]) -> str:
    lines: list[str] = []
    for i, c in enumerate(cues, 1):
        body = c.get("dub_text") or c["text"]
        lines.append(str(i))
        lines.append(f"{format_srt_time(c['start'])} --> {format_srt_time(c['end'])}")
        lines.append(body)
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Pack transcript/SRT into timed dub cues")
    ap.add_argument("source", type=Path, help="export-words JSON, Scribe JSON, or .srt")
    ap.add_argument("--output", type=Path, default=None, help="cues.json path")
    ap.add_argument("--srt-out", type=Path, default=None, help="Write source-language SRT")
    ap.add_argument("--silence-threshold", type=float, default=0.45,
                    help="Break a cue when the gap between speech tokens >= this (seconds)")
    ap.add_argument("--duration", type=float, default=None,
                    help="Override timeline duration (project duration from stat)")
    ap.add_argument("--target-language", default="", help="BCP-47 tag to stamp on cues.json")
    ap.add_argument("--dry-run", action="store_true", help="Print table, do not write files")
    args = ap.parse_args()

    src = args.source.resolve()
    if not src.exists():
        sys.exit(f"source not found: {src}")

    words, meta = load_words(src)
    cues = group_cues(words, args.silence_threshold)
    duration = args.duration if args.duration is not None else meta.get("timeline_duration") or 0.0

    payload = {
        "source": str(src),
        "source_format": meta.get("source_format"),
        "provider": meta.get("provider"),
        "source_language": meta.get("language") or "",
        "target_language": args.target_language,
        "timeline_duration": duration,
        "source_track_id": meta.get("source_track_id"),
        "source_clip_id": meta.get("source_clip_id"),
        "source_text": meta.get("source_text") or " ".join(c["text"] for c in cues),
        "silence_threshold": args.silence_threshold,
        "cues": [
            {
                "id": i,
                "start": round(c["start"], 3),
                "end": round(c["end"], 3),
                "duration": round(c["end"] - c["start"], 3),
                "text": c["text"],
                "dub_text": None,
                "speaker_id": c.get("speaker_id"),
            }
            for i, c in enumerate(cues, 1)
        ],
    }

    print(f"{len(cues)} cues  duration={duration:.3f}s  source={src.name}")
    print(f"{'id':>4}  {'start':>7}  {'end':>7}  {'dur':>6}  text")
    for c in payload["cues"]:
        print(f"{c['id']:4d}  {c['start']:7.3f}  {c['end']:7.3f}  {c['duration']:6.3f}  {c['text']}")

    if args.dry_run:
        return

    out = (args.output or (src.parent / "cues.json")).resolve()
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {out}")

    if args.srt_out:
        args.srt_out.resolve().write_text(render_srt(payload["cues"]), encoding="utf-8")
        print(f"wrote {args.srt_out.resolve()}")


if __name__ == "__main__":
    main()
