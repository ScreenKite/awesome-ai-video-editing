---
name: screenkite-audio-dub
description: >
  Dub a ScreenKite recording into another language with time-matched TTS.
  Transcribe the microphone track (ScreenKite export-words or ElevenLabs
  Scribe) to SRT / cue JSON, generate speech with Fish Audio (s2.1-pro-free)
  or ElevenLabs, fit each cue into the original start/end window, mute the
  original mic track, and import the mix as a language-tagged audio track.
  Use when the user asks to dub, translate narration, replace the voiceover,
  mute and swap the mic track, generate multilingual audio, Fish Audio TTS,
  ElevenLabs TTS dubbing, or time-matched dubbed audio on a .skbundle.
  Do NOT use for silence/filler cutting (see screenkite-clean-cut) or B-roll
  overlays (see use-screenkite-advanced-b-roll).
---

# screenkite-audio-dub

Replace a ScreenKite recording's spoken audio with a **time-matched** dub in
another language. Original pauses stay. Lip-ish alignment is per cue, not a
single stretched file.

```
1. export-words (or Scribe)     → word-level JSON
2. pack_cues.py                 → cues.json + source.srt
3. fill dub_text (agent/human)  → translated lines, same timestamps
4. gen_dub.py                   → mix.wav (TTS + speed fit + silence bed)
5. dry-run table                → confirm before mutating
6. apply_dub.py                 → mute mic + add language-tagged track
```

## Prerequisites

- `screenkite` CLI (`/usr/local/bin/screenkite`). Prefer `--project` on every call.
- `ffmpeg` + `ffprobe` on PATH.
- Python 3.10+ with `requests` — prefer `uv run --with requests`.
- **Fish Audio (default TTS):** `FISH_API_KEY` in a `.env` walking up from the
  bundle, `~/.config/env/*.env`, or the environment. Voice id via `--voice` or
  `FISH_VOICE_ID`. Get a key at https://fish.audio/app/api-keys
- **ElevenLabs fallback:** `ELEVEN_LABS_API_KEY` (underscored). ScreenKite's
  GUI already has this for `export-words`; the TTS path still needs the key in
  env. Optional `ELEVEN_VOICE_ID` (default George `JBFqnCBsd6RMkjVDRZzb`).

If the Fish key is missing, **ask for it** before generating. Only switch to
ElevenLabs when the user agrees or Fish is unavailable.

See `references/providers.md` for API details.

## Phase 1 — Inventory

```bash
PROJECT='/abs/path/to.skbundle'

screenkite tool call --name stat --project "$PROJECT" \
  --input-json '{"scope":"summary"}' --json
screenkite tool call --name ls-assets --project "$PROJECT" --json
screenkite tool call --name transcribe-ready --project "$PROJECT" --json
```

Note `project.duration`, the microphone `trackId` (usually contains `mic`),
and `projectRevision`. Do not map `sessions list` row numbers to
`--project-index`.

## Phase 2 — Transcribe

Prefer ScreenKite's word-level export (uses the GUI's ElevenLabs Scribe
config, returns **timeline** seconds after cuts):

```bash
EDIT="$PROJECT/../$(basename "$PROJECT" .skbundle)-dub"
mkdir -p "$EDIT"

screenkite tool call --name export-words --project "$PROJECT" \
  --input-json "{\"path\":\"$EDIT/transcript.json\"}" --json
```

If export-words fails or the GUI has no word-level provider, fall back to
`../screenkite-transcription-cut/scripts/transcribe_mic.py` on
`<bundle>/media/microphone_*.m4a`.

This project's transcription may be short, noisy, or wrong. **Show the source
text to the user** before translating. Offer `export-words` with
`"force": true` if they want a fresh ASR pass.

## Phase 3 — Pack cues + source SRT

```bash
uv run skills/screenkite-audio-dub/scripts/pack_cues.py \
  "$EDIT/transcript.json" \
  --duration <project.duration from stat> \
  --target-language en \
  --output "$EDIT/cues.json" \
  --srt-out "$EDIT/source.srt"
```

`--silence-threshold` default `0.45`. Raise it to merge more speech onto fewer
cues; lower it to dub almost phrase-by-phrase (better time-match, choppier
prosody). Punctuation-only tokens are treated as gaps.

Show the cue table. **Do not generate audio until dub_text is filled.**

## Phase 4 — Translate (mandatory review)

Copy `cues.json` and fill every `dub_text` with the target-language line.
Keep one cue per original window — do not merge/split cues after packing,
or the mix will miss the pause structure.

Rules for `dub_text`:

- Match meaning, not word count. A 1.2s Chinese cue cannot hold a long English
  sentence; shorten.
- Preserve product names / code identifiers.
- Leave `start` / `end` untouched.

Write `$EDIT/dub.srt` from the same timestamps (gen_dub.py also emits one).

Show the before/after table. **Wait for the user to confirm the translation.**

## Phase 5 — Generate time-matched mix

```bash
# List Fish voices if FISH_VOICE_ID is unset
uv run --with requests skills/screenkite-audio-dub/scripts/gen_dub.py \
  --provider fish --list-voices

uv run --with requests skills/screenkite-audio-dub/scripts/gen_dub.py \
  "$EDIT/cues.json" \
  --provider fish \
  --voice "$FISH_VOICE_ID" \
  --out-dir "$EDIT/dub"
```

ElevenLabs fallback:

```bash
uv run --with requests skills/screenkite-audio-dub/scripts/gen_dub.py \
  "$EDIT/cues.json" \
  --provider elevenlabs \
  --out-dir "$EDIT/dub"
```

How time-matching works:

1. TTS each cue at speed 1.0.
2. If duration drifts > 8% from the original window, regenerate with
   `prosody.speed` (Fish 0.5–2.0) or ElevenLabs `voice_settings.speed`.
3. If still long, `ffmpeg atempo`.
4. If still long, hard-trim (reported as `clipped`) — shorten `dub_text`.
5. If short, pad silence *inside the window* (next cue still starts on time).
6. Mix onto a silent bed of `timeline_duration` so original pauses remain.

`--dry-run` prints the plan without calling TTS. After a real run, inspect
`$EDIT/dub/report.json`: `clipped_cue_ids` and `max_abs_drift_s`. If anything
is clipped, rewrite those lines and regenerate **before** applying.

## Phase 6 — Dry-run apply (mandatory)

```bash
uv run skills/screenkite-audio-dub/scripts/apply_dub.py \
  --project "$PROJECT" \
  --mix "$EDIT/dub/mix.wav" \
  --cues "$EDIT/cues.json" \
  --language en \
  --dry-run
```

Confirm the mute target is the microphone, not system audio. **Do not apply
until the user confirms.**

## Phase 7 — Apply

```bash
uv run skills/screenkite-audio-dub/scripts/apply_dub.py \
  --project "$PROJECT" \
  --mix "$EDIT/dub/mix.wav" \
  --cues "$EDIT/cues.json" \
  --language en
```

This:

1. `props` `mute: true` on the original mic track.
2. `add` `type=audio` with `createTrack: {name, language}` so ScreenKite's
   language-grouped audio export treats the dub as its own language.

Undo: `edit-timeline` `action=undo` (once per mutation — mute, then add).
To hear the original again without undo, `props` `mute: false` on the mic
track, or mute the new dub track.

Optional captions from the dubbed SRT:

```bash
REV=$(screenkite tool call --name stat --project "$PROJECT" \
  --input-json '{"scope":"summary"}' --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["projectRevision"])')
screenkite tool call --name fx --project "$PROJECT" --input-json "{
  \"type\": \"captions\",
  \"action\": \"import\",
  \"expectedProjectRevision\": \"$REV\",
  \"config\": {\"path\": \"$EDIT/dub/dub.srt\", \"format\": \"srt\", \"confirm\": true}
}" --json
```

## Anti-patterns

- **Don't TTS the whole script as one file.** Pauses collapse and cues drift.
- **Don't skip the translation review.** Bad ASR (Cloud vs Claude, etc.) ships
  into the dub.
- **Don't mute system audio** unless the user asked — only the mic track.
- **Don't apply without dry-run.** `props` mute + `add` are undoable one step
  at a time, but easy to stack.
- **Don't rely on a stale default project.** Pass `--project` every call.
- **Don't ignore clipped cues.** A hard trim eats the end of a sentence.
  Shorten `dub_text` and regenerate that cue.
- **Don't call `fx voiceover/replace` for a multilingual dub.** That swaps
  the main spoken audio without a language tag. Prefer `add` + `createTrack`.
  Use `voiceover/replace` only when the user wants an in-place replacement
  with no extra track.

## When the clip is too short / empty

A 4-second test recording is a valid smoke test: pack → one or two cues →
generate → apply. If `export-words` returns almost no speech, stop and ask
whether to force-retranscribe or pick a different project.
