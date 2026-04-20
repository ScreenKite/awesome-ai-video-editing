#!/usr/bin/env python3
"""Scaffold N Hyperframes slot directories under a broll root.

Each slot_XX/ gets:
  - hyperframes.json  (minimal stub — 1920x1080@30fps, duration placeholder)
  - assets/           (empty; user drops logos/images here)
  - renders/          (created lazily by hyperframes render)

index.html is NOT created here — parallel sub-agents write it in Phase 6.

Usage:
    python3 scaffold_slots.py <broll_dir> <count>
    python3 scaffold_slots.py <broll_dir> 7 --duration 5.5
    python3 scaffold_slots.py <broll_dir> 7 --start 3      # start numbering at 03
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


STUB = {
    "version": 1,
    "name": "",  # filled per slot
    "compositions": [
        {
            "id": "main",
            "source": "index.html",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "duration": 5.5,
        }
    ],
}


def write_stub(slot_dir: Path, slot_name: str, duration: float) -> None:
    slot_dir.mkdir(parents=True, exist_ok=True)
    (slot_dir / "assets").mkdir(exist_ok=True)
    (slot_dir / "renders").mkdir(exist_ok=True)

    stub = json.loads(json.dumps(STUB))
    stub["name"] = slot_name
    stub["compositions"][0]["duration"] = duration

    hf = slot_dir / "hyperframes.json"
    if hf.exists():
        print(f"  skip existing: {hf}")
        return
    hf.write_text(json.dumps(stub, indent=2) + "\n")
    print(f"  created: {hf}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("broll_dir", type=Path, help="Root directory to create slot_XX/ under")
    ap.add_argument("count", type=int, help="Number of slots to create")
    ap.add_argument("--duration", type=float, default=5.5,
                    help="Default composition duration (seconds). Sub-agents override per slot.")
    ap.add_argument("--start", type=int, default=1,
                    help="Starting slot number (default 1 -> slot_01)")
    args = ap.parse_args()

    if args.count < 1:
        sys.exit("count must be >= 1")

    root = args.broll_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    print(f"scaffolding {args.count} slots under {root}")

    for i in range(args.count):
        num = args.start + i
        name = f"slot_{num:02d}"
        write_stub(root / name, name, args.duration)

    print(f"done. next: write index.html in each slot (Phase 6), "
          f"then cd slot_XX && npx hyperframes render --output renders/{name}.mp4")


if __name__ == "__main__":
    main()
