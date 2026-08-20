# TTS providers

## Fish Audio (default)

- Docs: https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech
- Endpoint: `POST https://api.fish.audio/v1/tts`
- Auth: `Authorization: Bearer $FISH_API_KEY`
- Model header: `model: s2.1-pro-free` (free developer tier; production is `s2.1-pro`)
- Voice: `reference_id` (library model id or a clone you trained)
- Time control: `prosody.speed` in **0.5–2.0** (1.0 = normal, 2.0 = twice as fast)
- Output: request `format: wav`, `sample_rate: 44100` so ffmpeg can mix without a transcode surprise

```bash
curl -X POST https://api.fish.audio/v1/tts \
  -H "Authorization: Bearer $FISH_API_KEY" \
  -H "Content-Type: application/json" \
  -H "model: s2.1-pro-free" \
  -d '{
    "text": "[calm] One. Let me test this.",
    "reference_id": "YOUR_VOICE_ID",
    "format": "wav",
    "sample_rate": 44100,
    "prosody": {"speed": 1.0, "volume": 0, "normalize_loudness": true}
  }' \
  --output cue.wav
```

List voices: `GET https://api.fish.audio/model?page_size=20&sort_by=task_count`
(or `gen_dub.py --provider fish --list-voices`).

S2 bracket direction (`[excited]`, `[laughing]`) is allowed in `text`. Do not
put direction tags in `dub_text` unless the user asked — they consume cue time.

## ElevenLabs (fallback)

- TTS: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
- Auth: `xi-api-key: $ELEVEN_LABS_API_KEY`
- Default model: `eleven_multilingual_v2`
- Default voice: `JBFqnCBsd6RMkjVDRZzb` (George)
- Time control: `voice_settings.speed` (API allows 0.25–4.0; this skill clamps
  regenerate-to-fit to **0.7–1.2** so it stays natural, then uses ffmpeg
  `atempo` if still long)

Scribe STT (word-level, used by ScreenKite `export-words` and
`transcribe_mic.py`) is a different product. A working GUI transcription
key does not automatically mean `gen_dub.py --provider elevenlabs` has the
key in the process environment — still load `ELEVEN_LABS_API_KEY`.

## Time-matching contract

The mix file **must** be `timeline_duration` seconds (± one frame). Each cue
starts at its original `start`. Never close the gap between cues by
concatenating TTS clips back-to-back.

Prefer shortening `dub_text` over aggressive `atempo` (>1.25) or clipping.
