---
name: use-screenkite-advanced-b-roll
description: End-to-end pipeline for adding short animated B-roll overlays to a ScreenKite screen recording using the advanced DSL scene layout. Transcribes the microphone audio with ElevenLabs Scribe, proofreads product names via web search, plans brief corner-PiP visual moments, generates each visual with Hyperframes (HTML + GSAP) via parallel sub-agents, renders to MP4, and composites via ScreenKite's setSceneLayout with magicMove transitions. Use when (1) the user opens or references a .skbundle ScreenKite recording and wants animated B-roll accents on top of screen + camera, (2) the user says "add B-roll", "advanced layout", "overlay visuals", "plan visuals for this recording", "ScreenKite DSL", (3) the user wants transcript-driven visual planning where visuals are brief corner accents rather than full-frame takeovers.
---

# use-screenkite-advanced-b-roll

## Purpose

Layer short, animated B-roll visuals on top of a ScreenKite recording's screen+camera composition. The **screen recording stays the main content**; B-roll is a brief accent (4–6s corner PiP) that appears, lets the viewer read it, then disappears via magicMove.

## Pipeline (7 phases)

```
1. Locate mic audio in .skbundle
2. Transcribe with ElevenLabs Scribe  → word-level JSON
3. Pack to phrase view  + proofread via web search
4. Propose visual idea menu with density bundles
5. Scaffold N Hyperframes projects (one per visual slot)
6. Dispatch parallel sub-agents → each writes one index.html
7. Render each to MP4  →  apply setSceneLayout DSL with magicMove
```

## Prerequisites (check before starting)

- **ScreenKite.app** at `/Applications/ScreenKite.app` (macOS).
- **Node ≥ 22** and **FFmpeg** on PATH.
- **`ELEVEN_LABS_API_KEY`** in project `.env` (note: *not* `ELEVENLABS_API_KEY` — this repo uses the underscored form).
- **Hyperframes CLI** — invoked via `npx hyperframes` (auto-installs on first use). Repo: https://github.com/heygen-com/hyperframes
- **Hyperframes agent skills** (optional but helpful for sub-agents): `npx skills add heygen-com/hyperframes` — registers `hyperframes`, `hyperframes-cli`, `gsap` skills.
- **video-use helpers** (bundled copies at `scripts/transcribe_mic.py` and `scripts/pack_transcripts.py`; upstream: https://github.com/browser-use/video-use).

If anything is missing, instruct the user to install it before proceeding. See `references/external-tools.md`.

## Phase 1 — Locate mic audio

A ScreenKite `.skbundle` is a directory. Mic audio lives at `<bundle>/media/microphone_*.m4a`. Screen at `<bundle>/media/screen_*.mp4`, camera at `<bundle>/media/camera_*.mov`, system audio at `<bundle>/media/system_audio_*.m4a`.

Confirm the project is open in ScreenKite (so later CLI calls have a current project):

```bash
'/Applications/ScreenKite.app/Contents/MacOS/ScreenKite' agent project open --path '<bundle path>' --json
'/Applications/ScreenKite.app/Contents/MacOS/ScreenKite' agent project current --json
```

## Phase 2 — Transcribe

Use `scripts/transcribe_mic.py` — a thin wrapper over ElevenLabs Scribe that reads `ELEVEN_LABS_API_KEY` from the project `.env` and caches per-source.

```bash
python3 scripts/transcribe_mic.py \
  '<bundle>/media/microphone_dji-mic-mini.m4a' \
  --edit-dir '<bundle-parent>/<project-slug>-edit' \
  --language zho \
  --num-speakers 1
```

Output: `<edit-dir>/transcripts/microphone_*.json` (word-level, diarized, audio events, ~155KB for 3 minutes).

Cached: skips re-upload if output exists.

## Phase 3 — Pack and proofread

### 3a. Pack to phrase-level view

```bash
python3 scripts/pack_transcripts.py --edit-dir '<edit-dir>'
```

Produces `<edit-dir>/takes_packed.md` — phrases break on silences ≥ 0.5s. 10× more compact than raw JSON.

### 3b. Proofread — MANDATORY for any English product/proper nouns

ASR often misrecognizes proper nouns when the speaker mixes languages. In one derived session, Scribe consistently heard "Claude" as "Cloud" throughout a Chinese recording. Every such misrecognition propagates into the generated visuals.

**Rule:** Before Phase 4, scan the packed transcript for any English word that looks like a product name. For each one, use WebSearch to verify:

- Is this a real product with that exact spelling?
- Is the context consistent (launch date, capabilities, positioning)?
- What is the canonical capitalization?

Write the corrected version to `<edit-dir>/takes_packed_proofread.md` with a small diff table showing what was corrected and why.

**Do NOT skip this step, even if it looks obvious.** Seven visuals with the wrong product name waste 15+ minutes of render time.

## Phase 4 — Visual idea menu + density

1. **Propose the menu.** Read `references/visual-ideas-menu.md` for a long list of beat-appropriate visuals. Propose a menu organized by beat (intro / tool-name / analogy / feature-highlight / pricing / outro etc.).

2. **Offer density bundles:**

| Density | Count | Pace | When |
|---|---|---|---|
| Sparse | 4 | ~40s apart | Documentary feel |
| Medium | 7 | ~24s apart | Default — balanced |
| Dense | 11–13 | ~13s apart | Explainer energy |
| Hyper | 15+ | phrase-level | Short-form retention-max |

**Default to Medium (7)** unless the user asks otherwise. B-roll is an accent on a screen-recording tutorial, not the main act.

3. **Wait for confirmation.** Do not scaffold until the user approves a bundle.

## Phase 5 — Scaffold N Hyperframes projects

One Hyperframes project per slot, all under `<video-project-root>/broll/slot_XX/`:

```
broll/
├── slot_01/
│   ├── hyperframes.json
│   ├── index.html          (written in Phase 6)
│   └── assets/              (logos, images referenced by index.html)
├── slot_02/ ... slot_NN/
```

Use `scripts/scaffold_slots.py <broll-dir> <count>` to create the directories with `hyperframes.json` stubs. Copy logo/asset files into the appropriate `slot_XX/assets/` folder if a slot needs them (e.g., ScreenKite self-promo).

## Phase 6 — Parallel sub-agents build each index.html

Dispatch N sub-agents **in a single message** (each Agent tool call inside one response = parallel). Each agent brief must be fully self-contained. Use `references/subagent-brief-template.md` as the template — it encodes every hard rule below.

### Hard rules every brief must carry

See `references/hyperframes-contract.md` for the full list. The critical ones:

1. **Content fills the full 1920×1080 MP4 frame.** The MP4 IS the PiP — when ScreenKite places it with `placeSelf="topRight" width="40%"`, the whole frame lands in the corner. Do not put content in a sub-corner of the MP4 (it'll be buried in a corner-of-a-corner). Warm cream full-bleed background, content centered and sized to fill.

2. **Timeline shape: entry → settled hold → NO internal exit.** ScreenKite's `magicMove` handles the exit. If the composition has its own exit animation, viewers see a double-exit. Structure:
   - `0.0 – 1.5s`: entry animations (pop, slide, bounce)
   - `1.5 – end`: settled hold — visual is fully readable, minimal ambient motion
   - Do NOT add a fade/scale-out in the last 0.5s.

3. **Composition duration ≥ DSL window duration + 1.5–2s reading hold.** The viewer needs time to read after the entry finishes. A 5s DSL window needs at least 3.5s of post-entry hold. Don't make visuals flash by.

4. **Synchronous timeline, paused, registered at `window.__timelines["main"]`.** No `async`, `setTimeout`, `Promise`. No `Math.random`, `Date.now`, `repeat: -1`. Finite repeat counts only: `repeat: Math.ceil(holdLen / cycleLen) - 1`.

5. **Standalone composition (no `<template>` wrapper).** Root div directly in `<body>`. See `references/dsl-cookbook.md` for the boilerplate.

6. **Lint before reporting done.** Each agent runs `npx hyperframes lint --json` from the slot directory, fixes errors, reports warnings.

### Launching sub-agents

Launch in ONE message with N Agent tool calls, all `run_in_background: true`. Each prompt:
- Absolute output path: `<broll>/slot_XX/index.html`
- Slot content spec (what to show, what text, what icons)
- Palette (hex values — no "choose a color")
- Font sizes (LARGE — display 160-220px, body 48-72px)
- Duration and timeline beats
- Asset paths if applicable (logos, images)
- The hard rules above
- "Do NOT ask questions. If ambiguous, pick the most obvious warm/cute interpretation."

## Phase 7 — Render + apply DSL

### 7a. Render serially

Each `npx hyperframes render` spawns Chrome. Running in parallel causes contention. Serial is fine — a 30s composition renders in 30–50s:

```bash
for i in $(seq -w 01 07); do
  ( cd broll/slot_$i && npx hyperframes render --output renders/slot_$i.mp4 --quality standard )
done
```

Quality: use `standard` for review, `high` for final delivery, `draft` for fast iteration.

### 7b. Plan DSL windows (brief + reading hold)

Default placement rotation for N=7:
- Slot 1: `bottomLeft 40%` (lower-third), 3.6s
- Slots 2, 3, 5, 7: `topRight` 38–45%, 5–5.5s
- Slots 4, 6: `topLeft` 40–42%, 4.5–6s

Camera stays at `bottomRight 22% aspect=3:4` across all slots for continuity.

Each slot's display window should be **entry + reading hold**, not the composition's full duration. If a composition is 12s long (entry 1.5s + long hold), a 5s display window shows entry + 3.5s hold, then magicMove takes over.

### 7c. Apply setSceneLayout

Use `scripts/apply_broll_dsl.py` — reads a plan JSON, applies each via the ScreenKite CLI, then clears any old tails.

```bash
python3 scripts/apply_broll_dsl.py <plan.json>
```

See `references/dsl-cookbook.md` for the plan.json schema and ready-to-copy DSL snippets.

### 7d. The tail-clearing gotcha

`setSceneLayout` **splits** existing segments; it does not replace. If you previously applied a 22-second advanced segment and now re-apply a 5-second one at the same start, you end up with a new 5s segment + a 17s leftover tail still showing advanced mode. The tails must be cleared by calling setSceneLayout with `mode: "pictureInPicture"` on each tail range.

`apply_broll_dsl.py` handles this automatically: after applying new B-roll windows, it reads the layout state, finds any `advanced` segments NOT matching the intended plan, and reverts them to PiP.

### 7e. Verify

```bash
'/Applications/ScreenKite.app/Contents/MacOS/ScreenKite' agent tool call \
  --name getProjectState --input-json '{"scope":"layout"}' --json
```

Confirm exactly N `advanced` segments at the intended ranges, with `pictureInPicture` everywhere else. Open ScreenKite and scrub to visually verify.

## Iteration

If a visual is wrong (content, timing, placement):

1. Edit `broll/slot_XX/index.html` (or regenerate via a targeted sub-agent)
2. Re-render: `cd broll/slot_XX && npx hyperframes render --output renders/slot_XX.mp4`
3. Update the plan.json and re-run `apply_broll_dsl.py` (it's idempotent — tails get re-cleared)

The ScreenKite DSL references the MP4 by absolute path, so replacing the file is enough for timing-unchanged iterations.

## References (load on demand)

- `references/external-tools.md` — installation/repo URLs for every prerequisite
- `references/dsl-cookbook.md` — DSL snippets per placement + plan.json schema
- `references/hyperframes-contract.md` — all hard rules for composition authoring
- `references/visual-ideas-menu.md` — beat-by-beat idea catalog + density bundles
- `references/subagent-brief-template.md` — self-contained brief template for parallel agents

## Scripts (runnable, token-efficient)

- `scripts/transcribe_mic.py` — ElevenLabs Scribe wrapper, cached, uses `ELEVEN_LABS_API_KEY`
- `scripts/pack_transcripts.py` — phrase-level packing from raw Scribe JSON
- `scripts/scaffold_slots.py` — create N slot dirs with hyperframes.json stubs
- `scripts/apply_broll_dsl.py` — apply setSceneLayout from plan JSON + clear tails
- `scripts/find_skbundle_mic.py` — locate mic audio inside a .skbundle

## Anti-patterns

- **Don't skip the proofreading step.** Scribe will get English proper nouns wrong in Chinese/ZH-TW recordings; verify before generating visuals that say "Cloud" instead of "Claude".
- **Don't position content in a corner of the MP4.** The MP4 is the corner. Content fills the frame.
- **Don't let a composition exit animate inside its own frame.** magicMove handles exit. Internal exits produce double-fades.
- **Don't re-apply setSceneLayout without clearing tails.** You'll end up with zombie B-roll playing for the full original window.
- **Don't render in parallel.** Chrome contention. Serial is fast enough.
- **Don't re-transcribe cached sources.** Immutable input → immutable output. Scribe costs money.
- **Don't start rendering before the user confirms density + bundle picks.** Re-work is expensive.
- **Don't use Remotion here** if Hyperframes is already installed. Stick to one tool for this skill.
