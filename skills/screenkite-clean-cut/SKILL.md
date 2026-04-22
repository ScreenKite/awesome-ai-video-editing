---
name: screenkite-clean-cut
description: >
  Transcribe a ScreenKite recording's mic audio, then remove BOTH silence gaps
  AND filler words (um, uh, ah, er, hmm) from the timeline in a single merged
  editTimeline cut. Use when the user asks to "clean up audio", "remove filler
  words", "remove ums and uhs", "cut dead air and fillers", or "full auto-cut"
  on a .skbundle project. Combines screenkite-transcription-cut silence removal
  with filler-word detection into one dry-run → confirm → apply flow.
  Do NOT use for B-roll overlay work (see use-screenkite-advanced-b-roll).
  Do NOT use when no .skbundle is open.
---

# screenkite-clean-cut

Remove **silence gaps** and **filler words** (um, uh, ah, er, hmm) from a
ScreenKite recording in a single pass — one transcript, one dry-run, one cut.

## Prerequisites

- `screenkite` CLI at `/usr/local/bin/screenkite-alpha` (or `screenkite`).
- `ELEVEN_LABS_API_KEY` (underscored) in a `.env` anywhere up from the bundle,
  or exported in the shell environment.
- `ffmpeg` on PATH.
- `python3` + `requests` — use `uv run --with requests` to avoid install issues.

## Phase 1 — Open project

```bash
'/usr/local/bin/screenkite-alpha' agent project open \
  --path '<absolute-path-to.skbundle>' --json
```

Confirm the project is current:

```bash
'/usr/local/bin/screenkite-alpha' agent project current --json
```

## Phase 2 — Transcribe mic audio

Mic audio lives at `<bundle>/media/microphone_*.m4a`.

```bash
# Source .env first if key is not in the shell
set -a && source /path/to/workspace/.env && set +a

uv run --with requests \
  .agents/skills/screenkite-clean-cut/scripts/transcribe_mic.py \
  '<bundle>/media/microphone_<name>.m4a' \
  --edit-dir '<bundle-parent>/<slug>-edit' \
  --language en \
  --num-speakers 1
# Output: <edit-dir>/transcripts/<stem>.json  (word-level, cached)
```

> Re-running is a no-op if the transcript JSON already exists.

## Phase 3 — Dry-run (mandatory — show user before applying)

```bash
uv run --with requests \
  .agents/skills/screenkite-clean-cut/scripts/compute_all_cuts.py \
  '<edit-dir>/transcripts/<stem>.json' \
  --min-silence 0.8 \
  --silence-pad 0.15 \
  --filler-pad 0.03 \
  --dry-run
```

Output shows two sections: **Silence gaps** and **Filler words**, then a
combined summary. Show the full table to the user. **Do not apply cuts until
the user confirms.**

Tuning knobs:
| Flag | Default | Notes |
|------|---------|-------|
| `--min-silence` | `0.8` | Gaps shorter than this are kept |
| `--silence-pad` | `0.15` | Kept at each edge of a silence gap |
| `--filler-pad` | `0.03` | Kept at each edge of a filler word |
| `--fillers` | `um,uh,ah,er,hmm,hm` | Comma-separated list to override |

## Phase 4 — Apply cuts

All silence + filler ranges are merged and sorted before the single
`editTimeline` call, so there is no ordering issue with existing timeline edits.

```bash
'/usr/local/bin/screenkite-alpha' agent tool call \
  --name editTimeline \
  --input-json "$(uv run --with requests \
      .agents/skills/screenkite-clean-cut/scripts/compute_all_cuts.py \
      '<edit-dir>/transcripts/<stem>.json' \
      --min-silence 0.8 --silence-pad 0.15 --filler-pad 0.03 \
      --emit-tool-input)" \
  --json
```

Or save cuts first and apply separately:

```bash
# Save
uv run --with requests \
  .agents/skills/screenkite-clean-cut/scripts/compute_all_cuts.py \
  '<edit-dir>/transcripts/<stem>.json' \
  --min-silence 0.8 --silence-pad 0.15 --filler-pad 0.03 \
  --output '<edit-dir>/all_cuts.json'

# Apply
python3 .agents/skills/screenkite-clean-cut/scripts/apply_cuts.py \
  '<edit-dir>/all_cuts.json'
```

## Phase 5 — Verify

```bash
'/usr/local/bin/screenkite-alpha' agent tool call \
  --name getProjectState --input-json '{"scope":"summary"}' --json
```

Check that `duration` shrank by roughly the total removed seconds.

To undo: `editTimeline action=undo` — one call per cut, last-in-first-out.

## Key differences from screenkite-transcription-cut

| | screenkite-transcription-cut | screenkite-clean-cut |
|---|---|---|
| Removes silences | ✅ | ✅ |
| Removes filler words | ❌ | ✅ |
| Scripts | compute_silence_cuts.py | compute_all_cuts.py |
| Cuts per pass | silence only | silence + fillers merged |

## Anti-patterns

- **Never skip the dry-run.** Cuts are destructive; undo is one-step-at-a-time.
- **Don't set `--min-silence` below 0.3s.** Feels choppy.
- **Don't set `--filler-pad` below 0.02s.** Audio clicks at splice points.
- **Don't run without an open project.** CLI calls silently fail.
- **Don't add words like "like", "right", "so" to `--fillers` without review.**
  Context-dependent words cause many false positives. Stick to hesitation sounds.
