#!/usr/bin/env python3
"""Transcribe a microphone audio file with ElevenLabs Scribe.

Uses ELEVEN_LABS_API_KEY (underscored form) from project .env or environment.
Extracts mono 16kHz WAV via ffmpeg, uploads to Scribe with verbatim +
diarize + audio events + word-level timestamps, writes full response to
<edit_dir>/transcripts/<stem>.json.

Cached: if the output file already exists, upload is skipped.

Usage:
    python3 transcribe_mic.py <audio_or_video_path>
    python3 transcribe_mic.py <audio> --edit-dir /custom/edit
    python3 transcribe_mic.py <audio> --language zho --num-speakers 1
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

SCRIBE_URL = "https://api.elevenlabs.io/v1/speech-to-text"
ENV_KEYS = ("ELEVEN_LABS_API_KEY", "ELEVENLABS_API_KEY")


def load_api_key(start_dir: Path) -> str:
    """Look for ELEVEN_LABS_API_KEY (preferred) or ELEVENLABS_API_KEY in
    any .env from start_dir walking up to /, then fall back to environment."""
    seen: set[Path] = set()
    cur = start_dir.resolve()
    while True:
        env_path = cur / ".env"
        if env_path.exists() and env_path not in seen:
            seen.add(env_path)
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                if k in ENV_KEYS:
                    return v.strip().strip('"').strip("'")
        if cur.parent == cur:
            break
        cur = cur.parent

    for k in ENV_KEYS:
        v = os.environ.get(k)
        if v:
            return v
    sys.exit(
        "ELEVEN_LABS_API_KEY (or ELEVENLABS_API_KEY) not found in any .env "
        "walking up from the audio file, or in the environment."
    )


def extract_audio(src: Path, dest: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def call_scribe(
    audio_path: Path,
    api_key: str,
    language: str | None,
    num_speakers: int | None,
) -> dict:
    data: dict[str, str] = {
        "model_id": "scribe_v1",
        "diarize": "true",
        "tag_audio_events": "true",
        "timestamps_granularity": "word",
    }
    if language:
        data["language_code"] = language
    if num_speakers:
        data["num_speakers"] = str(num_speakers)

    with open(audio_path, "rb") as f:
        resp = requests.post(
            SCRIBE_URL,
            headers={"xi-api-key": api_key},
            files={"file": (audio_path.name, f, "audio/wav")},
            data=data,
            timeout=1800,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Scribe returned {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def transcribe_one(
    src: Path,
    edit_dir: Path,
    api_key: str,
    language: str | None = None,
    num_speakers: int | None = None,
    verbose: bool = True,
) -> Path:
    transcripts_dir = edit_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcripts_dir / f"{src.stem}.json"

    if out_path.exists():
        if verbose:
            print(f"cached: {out_path}")
        return out_path

    if verbose:
        print(f"  extracting audio from {src.name}", flush=True)

    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / f"{src.stem}.wav"
        extract_audio(src, wav)
        size_mb = wav.stat().st_size / (1024 * 1024)
        if verbose:
            print(f"  uploading {wav.name} ({size_mb:.1f} MB)", flush=True)
        payload = call_scribe(wav, api_key, language, num_speakers)

    out_path.write_text(json.dumps(payload, indent=2))
    dt = time.time() - t0

    if verbose:
        kb = out_path.stat().st_size / 1024
        print(f"  saved: {out_path} ({kb:.1f} KB) in {dt:.1f}s")
        if isinstance(payload, dict) and "words" in payload:
            print(f"    words: {len(payload['words'])}")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="ElevenLabs Scribe mic transcription")
    ap.add_argument("source", type=Path, help="Path to mic audio or video file")
    ap.add_argument(
        "--edit-dir", type=Path, default=None,
        help="Output directory (default: <source_parent>/edit)",
    )
    ap.add_argument(
        "--language", type=str, default=None,
        help="ISO language code (e.g. 'en', 'zho'). Omit to auto-detect.",
    )
    ap.add_argument(
        "--num-speakers", type=int, default=None,
        help="Number of speakers (improves diarization accuracy)",
    )
    args = ap.parse_args()

    src = args.source.resolve()
    if not src.exists():
        sys.exit(f"source not found: {src}")

    edit_dir = (args.edit_dir or (src.parent / "edit")).resolve()
    api_key = load_api_key(src.parent)

    transcribe_one(
        src=src,
        edit_dir=edit_dir,
        api_key=api_key,
        language=args.language,
        num_speakers=args.num_speakers,
    )


if __name__ == "__main__":
    main()
