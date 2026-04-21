#!/usr/bin/env python3
"""Apply ScreenKite setSceneLayout for each B-roll slot, then clear any
leftover advanced-mode tails (reverting them to pictureInPicture).

Reads a plan.json file describing the camera geometry + per-slot windows,
builds the advanced DSL per slot, and calls the ScreenKite agent CLI.

Plan schema (minimal):

{
  "broll_dir": "/abs/path/to/broll",
  "camera":    {"width": "22%", "aspect": "3:4", "placeSelf": "bottomRight"},
  "transition": "magicMove",
  "slots": [
    {"num": "01", "start": 1.4, "duration": 3.6,
     "placeSelf": "bottomLeft", "width": "40%"},
    {"num": "02", "start": 5.5, "duration": 5.0,
     "placeSelf": "topRight", "width": "42%"}
  ]
}

Per-slot optional fields (defaults in parens):
  aspect       ("16:9")
  contentMode  ("fit")
  transition   (plan.transition or "magicMove")
  source       (default: <broll_dir>/slot_<num>/renders/slot_<num>.mp4)

Usage:
    python3 apply_broll_dsl.py <plan.json>
    python3 apply_broll_dsl.py <plan.json> --dry-run       # print only
    python3 apply_broll_dsl.py <plan.json> --no-clear      # skip tail clearing
    python3 apply_broll_dsl.py <plan.json> --sk /path/to/ScreenKite
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_SK = "/Applications/ScreenKite.app/Contents/MacOS/ScreenKite"
EPS = 0.05  # seconds tolerance for matching planned ranges


def sk_call(sk: str, name: str, payload: dict) -> dict:
    """Invoke `ScreenKite agent tool call --name <name> --input-file <tmp>`."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        tmp_path = f.name
    try:
        cmd = [sk, "agent", "tool", "call", "--name", name,
               "--input-file", tmp_path, "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"{name} failed (exit {result.returncode}):\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        try:
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            return {"raw": result.stdout}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def build_dsl(camera: dict, slot: dict, source: str) -> str:
    cam_w = camera.get("width", "22%")
    cam_a = camera.get("aspect", "3:4")
    cam_p = camera.get("placeSelf", "bottomRight")

    v_w = slot.get("width", "40%")
    v_a = slot.get("aspect", "16:9")
    v_p = slot["placeSelf"]
    v_cm = slot.get("contentMode", "fit")

    return (
        '<SceneLayout version="2">'
        '<ZStack alignment="bottomRight">'
        '<ScreenKite.MainScreen />'
        f'<ScreenKite.Camera width="{cam_w}" aspect="{cam_a}" placeSelf="{cam_p}" />'
        f'<ScreenKite.Visual width="{v_w}" aspect="{v_a}" placeSelf="{v_p}" '
        f'contentMode="{v_cm}" source="{source}" />'
        '</ZStack>'
        '</SceneLayout>'
    )


def resolve_source(broll_dir: Path, slot: dict) -> str:
    if slot.get("source"):
        return str(Path(slot["source"]).resolve())
    num = slot["num"]
    return str((broll_dir / f"slot_{num}" / "renders" / f"slot_{num}.mp4").resolve())


def apply_slot(sk: str, plan: dict, slot: dict, dry_run: bool) -> tuple[float, float]:
    """Apply one advanced-mode segment. Returns (start, end)."""
    broll_dir = Path(plan["broll_dir"]).resolve()
    source = resolve_source(broll_dir, slot)
    if not Path(source).exists():
        raise FileNotFoundError(f"slot {slot['num']}: source missing: {source}")

    start = float(slot["start"])
    end = start + float(slot["duration"])
    dsl = build_dsl(plan.get("camera", {}), slot, source)
    transition = slot.get("transition") or plan.get("transition", "magicMove")

    payload = {
        "start": start,
        "end": end,
        "transition": transition,
        "dslSource": dsl,
    }
    print(f"slot {slot['num']}: {start:6.2f}->{end:6.2f}s  "
          f"{slot['placeSelf']:12s} {slot.get('width','40%'):>5s}  "
          f"{Path(source).name}")
    if dry_run:
        return start, end
    sk_call(sk, "setSceneLayout", payload)
    return start, end


def get_layout(sk: str) -> list[dict]:
    payload = {"scope": "layout"}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        tmp_path = f.name
    try:
        cmd = [sk, "agent", "tool", "call", "--name", "getProjectState",
               "--input-file", tmp_path, "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return data.get("layout", {}).get("segments", [])


def clear_tails(sk: str, planned: list[tuple[float, float]], dry_run: bool) -> int:
    """Revert any `advanced` segments NOT in the planned list to pictureInPicture."""
    segments = get_layout(sk)
    advanced = [s for s in segments if s.get("mode") == "advanced"]

    def matches_planned(seg: dict) -> bool:
        s = seg.get("start", -1.0)
        e = seg.get("end", -1.0)
        for ps, pe in planned:
            if abs(s - ps) < EPS and abs(e - pe) < EPS:
                return True
        return False

    tails = [s for s in advanced if not matches_planned(s)]
    if not tails:
        print("no tails to clear")
        return 0

    print(f"clearing {len(tails)} stray advanced segment(s):")
    for t in tails:
        s = t["start"]
        e = t["end"]
        print(f"  revert {s:6.2f}->{e:6.2f}s to pictureInPicture")
        if dry_run:
            continue
        sk_call(sk, "setSceneLayout", {
            "start": s, "end": e,
            "mode": "pictureInPicture",
            "transition": "magicMove",
        })
    return len(tails)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", type=Path, help="Path to plan.json")
    ap.add_argument("--sk", type=str, default=DEFAULT_SK,
                    help="Path to ScreenKite binary")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be applied without calling the CLI")
    ap.add_argument("--no-clear", action="store_true",
                    help="Skip clearing leftover advanced-mode tails")
    args = ap.parse_args()

    if not args.plan.is_file():
        sys.exit(f"plan not found: {args.plan}")

    plan = json.loads(args.plan.read_text())
    slots = plan.get("slots", [])
    if not slots:
        sys.exit("plan has no slots")

    if not args.dry_run and not Path(args.sk).exists():
        sys.exit(f"ScreenKite binary not found: {args.sk}")

    planned_ranges: list[tuple[float, float]] = []
    for slot in slots:
        planned_ranges.append(apply_slot(args.sk, plan, slot, args.dry_run))

    if args.no_clear:
        print("skipping tail clear (--no-clear)")
        return

    print()
    clear_tails(args.sk, planned_ranges, args.dry_run)

    if not args.dry_run:
        print()
        final = get_layout(args.sk)
        adv = [s for s in final if s.get("mode") == "advanced"]
        print(f"final: {len(adv)} advanced segment(s) on layout track "
              f"(expected {len(planned_ranges)})")


if __name__ == "__main__":
    main()
