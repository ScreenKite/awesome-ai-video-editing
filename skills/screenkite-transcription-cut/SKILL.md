---
name: screenkite-transcription-cut
description: >
  Transcribe a ScreenKite recording's mic audio, detect silence gaps in the
  word-level transcript, and cut those gaps from the timeline using
  editTimeline action=cut. Use when the user asks to "remove silences",
  "auto-cut dead air", "transcript-based cut", or "clean up pauses" in a
  .skbundle project. Do NOT use for B-roll overlay work (see
  use-screenkite-advanced-b-roll). Do NOT use when no .skbundle is open.
---

# screenkite-transcription-cut

Remove silence gaps from a ScreenKite recording based on the mic transcript.

## Prerequisites

- `screenkite` CLI at `/usr/local/bin/screenkite`.
- `ELEVEN_LABS_API_KEY` (underscored) in a `.env` anywhere up from the bundle.
- `ffmpeg` on PATH.
- `python3` + `requests` (`pip install requests`).

## Phase 1 — Open project

```bash
/usr/local/bin/screenkite agent project open \
  --path '<absolute-path-to.skbundle>' --json
```

Confirm the project is current:

```bash
/usr/local/bin/screenkite agent project current --json
```

## Phase 2 — Transcribe mic audio

Mic audio lives at `<bundle>/media/microphone_*.m4a`.

```bash
python3 scripts/transcribe_mic.py \
  '<bundle>/media/microphone_<name>.m4a' \
  --edit-dir '<bundle-parent>/<slug>-edit' \
  --language en \        # or zho, auto-detect if omitted
  --num-speakers 1
# Output: <edit-dir>/transcripts/<stem>.json  (word-level, cached)
```

> Script is a thin wrapper around ElevenLabs Scribe. Re-running is a no-op if
> the JSON already exists.

## Phase 3 — Compute silence cut ranges

```bash
python3 scripts/compute_silence_cuts.py \
  '<edit-dir>/transcripts/<stem>.json' \
  --min-silence 0.8 \       # seconds — gaps shorter than this are kept
  --pad 0.15 \              # seconds to keep at each edge of the gap
  --output '<edit-dir>/cuts.json'
```

Inspect `cuts.json` before applying. It lists `[{start, end, gap_s}, ...]`
sorted by start time. Adjust `--min-silence` if too many or too few cuts.

Typical values:
- `0.5s` — aggressive, catches short breath pauses
- `0.8s` — balanced default
- `1.5s` — conservative, only obvious dead air

## Phase 4 — Dry-run review (mandatory first pass)

```bash
python3 scripts/compute_silence_cuts.py \
  '<edit-dir>/transcripts/<stem>.json' \
  --min-silence 0.8 --pad 0.15 \
  --dry-run          # prints human-readable table, no file written
```

Show the table to the user. Confirm count and longest gaps look right.
**Do not apply cuts until the user confirms.**

## Phase 5 — Apply cuts

```bash
/usr/local/bin/screenkite agent tool call \
  --name editTimeline \
  --input-json "$(python3 scripts/compute_silence_cuts.py \
      '<edit-dir>/transcripts/<stem>.json' \
      --min-silence 0.8 --pad 0.15 --emit-tool-input)" \
  --json
```

`--emit-tool-input` prints `{"action":"cut","parameters":{"ranges":[...]}}`.

Or pass the saved `cuts.json` directly:

```bash
python3 scripts/apply_cuts.py '<edit-dir>/cuts.json'
```

`apply_cuts.py` reads cuts.json, calls the ScreenKite CLI, and prints the
updated clip count returned by the tool.

## Phase 6 — Verify

```bash
/usr/local/bin/screenkite agent tool call \
  --name getProjectState --input-json '{"scope":"summary"}' --json
```

Check `duration` shrank by roughly the total gap seconds. Scrub in ScreenKite
to spot-check.

If a cut is wrong: `editTimeline action=undo` (repeat per bad cut).

## Anti-patterns

- **Never run without dry-run first.** `cut` is destructive and undo is
  one-step-at-a-time.
- **Don't use the B-roll skill for this.** That skill uses `setSceneLayout`,
  which does not remove content.
- **Don't set `--min-silence` below 0.3s.** Sub-300ms gaps are rarely true
  dead air and cuts there feel choppy.
- **Don't cut without opening the project first.** CLI calls without a current
  project silently fail.
