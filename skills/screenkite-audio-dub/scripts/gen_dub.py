#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Generate time-matched dubbed audio from cues.json.

Each cue is synthesized independently (Fish Audio or ElevenLabs), then
speed-adjusted so it fits the original [start, end] window, then mixed
onto a silent bed of `timeline_duration` so original pauses stay intact.

Usage:
    python3 gen_dub.py cues.json --provider fish --voice YOUR_VOICE_ID
    python3 gen_dub.py cues.json --provider elevenlabs --dry-run
    python3 gen_dub.py --list-voices --provider fish
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

FISH_TTS_URL = "https://api.fish.audio/v1/tts"
FISH_MODELS_URL = "https://api.fish.audio/model"
ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
DEFAULT_ELEVEN_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # George — multilingual
DEFAULT_FISH_MODEL = "s2.1-pro-free"
FIT_TOLERANCE = 0.08  # regenerate if |gen/target - 1| > 8%
MAX_ATEMPO = 2.0
MIN_ATEMPO = 0.5


def load_env_value(names: tuple[str, ...], start_dir: Path) -> str | None:
    seen: set[Path] = set()
    search: list[Path] = []
    cur = start_dir.resolve()
    while True:
        search.append(cur)
        if cur.parent == cur:
            break
        cur = cur.parent
    search.append(Path.home() / ".config" / "env")
    search.append(Path.home())

    for folder in search:
        candidates = [folder / ".env"]
        if folder.name == "env":
            candidates.extend(sorted(folder.glob("*.env")))
        for env_path in candidates:
            if not env_path.exists() or env_path in seen:
                continue
            seen.add(env_path)
            for line in env_path.read_text(errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() in names:
                    val = v.strip().strip('"').strip("'")
                    if val:
                        return val
    for k in names:
        v = os.environ.get(k)
        if v:
            return v
    return None


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def atempo_chain(speed: float) -> str:
    """ffmpeg atempo only accepts 0.5–2.0; chain for values outside."""
    parts: list[str] = []
    s = speed
    while s > MAX_ATEMPO + 1e-9:
        parts.append("atempo=2.0")
        s /= 2.0
    while s < MIN_ATEMPO - 1e-9:
        parts.append("atempo=0.5")
        s /= 0.5
    parts.append(f"atempo={s:.6f}")
    return ",".join(parts)


def ffmpeg_atempo(src: Path, dest: Path, speed: float) -> None:
    filt = atempo_chain(speed)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-filter:a", filt, "-ar", "44100", "-ac", "1", str(dest)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def ffmpeg_to_wav(src: Path, dest: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(dest)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class FishProvider:
    name = "fish"
    speed_min, speed_max = 0.5, 2.0

    def __init__(self, api_key: str, voice: str, model: str) -> None:
        self.api_key = api_key
        self.voice = voice
        self.model = model

    def list_voices(self, language: str | None = None) -> list[dict]:
        params: dict = {"page_size": 20, "sort_by": "task_count"}
        if language:
            params["language"] = language
        resp = requests.get(
            FISH_MODELS_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            params=params,
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Fish list models {resp.status_code}: {resp.text[:400]}")
        items = resp.json().get("items") or []
        out = []
        for it in items:
            out.append({
                "id": it.get("_id") or it.get("id"),
                "title": it.get("title"),
                "languages": it.get("languages") or [],
                "task_count": it.get("task_count"),
            })
        return out

    def synthesize(self, text: str, dest: Path, speed: float) -> None:
        body = {
            "text": text,
            "reference_id": self.voice,
            "format": "wav",
            "sample_rate": 44100,
            "normalize": True,
            "prosody": {"speed": speed, "volume": 0, "normalize_loudness": True},
        }
        resp = requests.post(
            FISH_TTS_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "model": self.model,
            },
            json=body,
            timeout=180,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Fish TTS {resp.status_code}: {resp.text[:500]}")
        dest.write_bytes(resp.content)


class ElevenLabsProvider:
    name = "elevenlabs"
    speed_min, speed_max = 0.7, 1.2  # keep natural; wider 0.25–4 exists but sounds bad

    def __init__(self, api_key: str, voice: str, model: str) -> None:
        self.api_key = api_key
        self.voice = voice
        self.model = model

    def list_voices(self, language: str | None = None) -> list[dict]:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": self.api_key},
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ElevenLabs voices {resp.status_code}: {resp.text[:400]}")
        items = resp.json().get("voices") or []
        out = []
        for it in items:
            labels = it.get("labels") or {}
            langs = labels.get("language")
            out.append({
                "id": it.get("voice_id"),
                "title": it.get("name"),
                "languages": [langs] if langs else [],
                "task_count": None,
            })
        return out[:20]

    def synthesize(self, text: str, dest: Path, speed: float) -> None:
        url = ELEVEN_TTS_URL.format(voice_id=self.voice)
        body = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "speed": speed,
            },
        }
        resp = requests.post(
            url,
            headers={
                "xi-api-key": self.api_key,
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=180,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ElevenLabs TTS {resp.status_code}: {resp.text[:500]}")
        mp3 = dest.with_suffix(".mp3")
        mp3.write_bytes(resp.content)
        ffmpeg_to_wav(mp3, dest)
        mp3.unlink(missing_ok=True)


def fit_cue(provider, text: str, target_dur: float, work: Path, cue_id: int) -> dict:
    """Synthesize and fit one cue into target_dur. Never stretch more than atempo can handle."""
    if target_dur <= 0.05:
        raise RuntimeError(f"cue {cue_id} target duration {target_dur:.3f}s is too short")

    raw = work / f"cue_{cue_id:02d}_raw.wav"
    provider.synthesize(text, raw, speed=1.0)
    gen_dur = ffprobe_duration(raw)
    tts_speed = 1.0
    method = "passthrough"

    ratio = gen_dur / target_dur if target_dur else 1.0
    if abs(ratio - 1.0) > FIT_TOLERANCE:
        # Fish/Eleven speed: higher = faster = shorter. Want gen/target, clamped.
        tts_speed = clamp(ratio, provider.speed_min, provider.speed_max)
        fitted = work / f"cue_{cue_id:02d}_spd.wav"
        provider.synthesize(text, fitted, speed=tts_speed)
        gen_dur = ffprobe_duration(fitted)
        raw = fitted
        method = f"tts_speed={tts_speed:.3f}"
        ratio = gen_dur / target_dur

    out = work / f"cue_{cue_id:02d}.wav"
    if gen_dur > target_dur * (1.0 + FIT_TOLERANCE / 2):
        atempo = gen_dur / target_dur
        ffmpeg_atempo(raw, out, atempo)
        method = f"{method}+atempo={atempo:.3f}"
        gen_dur = ffprobe_duration(out)
    else:
        ffmpeg_to_wav(raw, out)
        gen_dur = ffprobe_duration(out)

    pad_s = max(0.0, target_dur - gen_dur)
    clipped = gen_dur > target_dur + 0.02
    if clipped:
        # Hard trim as last resort so the next cue is not overlapped.
        trimmed = work / f"cue_{cue_id:02d}_trim.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(out), "-t", f"{target_dur:.4f}",
             "-c:a", "pcm_s16le", str(trimmed)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        out = trimmed
        gen_dur = ffprobe_duration(out)
        pad_s = 0.0
        method += "+trim"

    return {
        "id": cue_id,
        "path": str(out),
        "gen_duration": round(gen_dur, 3),
        "target_duration": round(target_dur, 3),
        "pad_s": round(pad_s, 3),
        "tts_speed": round(tts_speed, 3),
        "method": method,
        "clipped": clipped,
        "drift_s": round(gen_dur - target_dur, 3),
    }


def mix_timeline(cues: list[dict], fits: list[dict], duration: float, dest: Path) -> None:
    """Place each fitted cue at its original start on a silent bed."""
    if duration <= 0:
        sys.exit("timeline_duration must be > 0")

    inputs: list[str] = ["-f", "lavfi", "-t", f"{duration:.4f}", "-i", "anullsrc=r=44100:cl=mono"]
    filters: list[str] = []
    mix_labels = ["[0:a]"]
    for i, (cue, fit) in enumerate(zip(cues, fits), 1):
        inputs.extend(["-i", fit["path"]])
        delay_ms = max(0, int(round(cue["start"] * 1000)))
        filters.append(f"[{i}:a]adelay={delay_ms}:all=1[a{i}]")
        mix_labels.append(f"[a{i}]")

    n = 1 + len(fits)
    filters.append(
        "".join(mix_labels) + f"amix=inputs={n}:duration=first:dropout_transition=0:normalize=0[out]"
    )
    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(filters),
        "-map", "[out]", "-t", f"{duration:.4f}",
        "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le",
        str(dest),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def srt_timestamp(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def render_dub_srt(cues: list[dict], dest: Path) -> None:
    lines: list[str] = []
    for i, c in enumerate(cues, 1):
        lines.append(str(i))
        lines.append(f"{srt_timestamp(c['start'])} --> {srt_timestamp(c['end'])}")
        lines.append((c.get("dub_text") or c["text"]).strip())
        lines.append("")
    dest.write_text("\n".join(lines), encoding="utf-8")


def build_provider(args, start_dir: Path):
    if args.provider == "fish":
        key = load_env_value(("FISH_API_KEY", "FISH_AUDIO_API_KEY"), start_dir)
        if not key:
            sys.exit(
                "FISH_API_KEY not found. Add it to a .env walking up from the cues file, "
                "~/.config/env/*.env, or the environment."
            )
        voice = args.voice or os.environ.get("FISH_VOICE_ID")
        if not voice:
            sys.exit(
                "Fish Audio needs --voice / FISH_VOICE_ID (a model reference_id). "
                "Run: python3 gen_dub.py --list-voices --provider fish"
            )
        return FishProvider(key, voice, args.fish_model), voice
    key = load_env_value(("ELEVEN_LABS_API_KEY", "ELEVENLABS_API_KEY"), start_dir)
    if not key:
        sys.exit("ELEVEN_LABS_API_KEY not found in .env / ~/.config/env / environment.")
    voice = args.voice or os.environ.get("ELEVEN_VOICE_ID") or DEFAULT_ELEVEN_VOICE
    return ElevenLabsProvider(key, voice, args.eleven_model), voice


def main() -> None:
    ap = argparse.ArgumentParser(description="Time-matched TTS mix from cues.json")
    ap.add_argument("cues_json", type=Path, nargs="?", help="cues.json with dub_text filled in")
    ap.add_argument("--provider", choices=("fish", "elevenlabs"), default="fish")
    ap.add_argument("--voice", default=None, help="Fish reference_id or ElevenLabs voice_id")
    ap.add_argument("--fish-model", default=DEFAULT_FISH_MODEL)
    ap.add_argument("--eleven-model", default="eleven_multilingual_v2")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate cues and print the plan; skip TTS")
    ap.add_argument("--list-voices", action="store_true")
    args = ap.parse_args()

    start_dir = (args.cues_json.parent if args.cues_json else Path.cwd())
    provider, voice = build_provider(args, start_dir)

    if args.list_voices:
        lang = None
        if args.cues_json and args.cues_json.exists():
            lang = json.loads(args.cues_json.read_text()).get("target_language") or None
        voices = provider.list_voices(language=lang or None)
        print(f"{provider.name} voices (voice id used as --voice):")
        for v in voices:
            langs = ",".join(v["languages"]) if v["languages"] else "-"
            print(f"  {v['id']}  {v['title']}  [{langs}]")
        return

    if not args.cues_json:
        sys.exit("cues.json is required unless --list-voices")
    cues_path = args.cues_json.resolve()
    plan = json.loads(cues_path.read_text())
    cues = plan.get("cues") or []
    missing = [c["id"] for c in cues if not (c.get("dub_text") or "").strip()]
    if missing:
        sys.exit(f"cues missing dub_text: {missing}. Translate first, then re-run.")
    duration = float(plan.get("timeline_duration") or 0)
    if duration <= 0:
        sys.exit("cues.json timeline_duration is missing; pass it from stat.project.duration")

    print(f"provider={provider.name}  voice={voice}  cues={len(cues)}  mix={duration:.3f}s")
    print(f"{'id':>4}  {'start':>7}  {'end':>7}  {'win':>6}  dub_text")
    for c in cues:
        print(f"{c['id']:4d}  {c['start']:7.3f}  {c['end']:7.3f}  {c['duration']:6.3f}  {c['dub_text']}")

    if args.dry_run:
        return

    out_dir = (args.out_dir or (cues_path.parent / "dub")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="dub-cues-"))
    fits = []
    try:
        for c in cues:
            target = float(c["end"]) - float(c["start"])
            print(f"  synthesizing cue {c['id']} ({target:.2f}s window)…", flush=True)
            fit = fit_cue(provider, c["dub_text"].strip(), target, work, c["id"])
            fit["start"] = c["start"]
            fit["end"] = c["end"]
            fit["text"] = c["text"]
            fit["dub_text"] = c["dub_text"]
            fits.append(fit)
            flag = " CLIPPED" if fit["clipped"] else ""
            print(
                f"    gen={fit['gen_duration']:.3f}s  pad={fit['pad_s']:.3f}s  "
                f"drift={fit['drift_s']:+.3f}s  {fit['method']}{flag}"
            )

        mix_path = out_dir / "mix.wav"
        mix_timeline(cues, fits, duration, mix_path)
        mix_dur = ffprobe_duration(mix_path)

        for f in fits:
            src = Path(f["path"])
            dest = out_dir / src.name
            if src.exists() and src.resolve() != dest.resolve():
                dest.write_bytes(src.read_bytes())
            f["path"] = str(dest)

        srt_path = out_dir / "dub.srt"
        render_dub_srt(cues, srt_path)

        report = {
            "provider": provider.name,
            "voice": voice,
            "timeline_duration": duration,
            "mix_duration": round(mix_dur, 3),
            "mix": str(mix_path),
            "srt": str(srt_path),
            "cues": fits,
            "clipped_cue_ids": [f["id"] for f in fits if f["clipped"]],
            "max_abs_drift_s": max((abs(f["drift_s"]) for f in fits), default=0.0),
        }
        report_path = out_dir / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"mix:    {mix_path}  ({mix_dur:.3f}s)")
        print(f"srt:    {srt_path}")
        print(f"report: {report_path}")
        if report["clipped_cue_ids"]:
            print(f"WARNING: clipped cues {report['clipped_cue_ids']} — shorten dub_text and regenerate")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
