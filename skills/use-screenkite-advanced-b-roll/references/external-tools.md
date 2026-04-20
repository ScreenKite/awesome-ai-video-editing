# External Tools

Everything this skill depends on, where to get it, and how to check whether it's already installed.

## Required

### 1. ScreenKite (macOS app)

The CLI we call from every phase lives inside the app bundle.

- **Check:** `test -x '/Applications/ScreenKite.app/Contents/MacOS/ScreenKite' && echo ok`
- **Install:** Download from https://screenkite.com (or the user's internal build channel)
- **Agent CLI help:** `'/Applications/ScreenKite.app/Contents/MacOS/ScreenKite' agent --help`

### 2. Node.js ≥ 22 + FFmpeg

Hyperframes requires Node 22+. FFmpeg is required for render and also by the transcribe helper.

- **Check:** `node --version && ffmpeg -version | head -1`
- **Install (macOS):** `brew install node ffmpeg`

### 3. Hyperframes CLI

HTML-based video composition framework.

- **Check:** `npx --yes hyperframes@latest --version`
- **Install:** Auto-installed on first `npx hyperframes` invocation. To pin globally: `npm install -g hyperframes`
- **Repo:** https://github.com/heygen-com/hyperframes
- **Docs:** https://hyperframes.heygen.com

### 4. ElevenLabs API key

Required for the Scribe speech-to-text step.

- **Check:** `grep -q ELEVEN_LABS_API_KEY <project>/.env && echo ok`
- **Get one:** https://elevenlabs.io → account → API keys
- **Install:** Add `ELEVEN_LABS_API_KEY=sk_...` to the project `.env` file (note the underscored form — NOT `ELEVENLABS_API_KEY`)

## Optional but recommended

### 5. Hyperframes agent skills (for sub-agents)

Installs `hyperframes`, `hyperframes-cli`, `gsap`, `hyperframes-registry`, `website-to-hyperframes` as Claude-code skills. When these are installed, parallel sub-agents writing composition HTML can trigger them automatically and produce better output.

- **Check:** look for `hyperframes` in available skills list
- **Install:** `npx skills add heygen-com/hyperframes`

### 6. video-use helpers (reference only — scripts are bundled)

This skill ships its own copies of `transcribe.py` and `pack_transcripts.py`. The upstream project has richer variants (batch transcription, timeline visualization) if you want to go deeper.

- **Repo:** https://github.com/browser-use/video-use
- **Install:** `git clone https://github.com/browser-use/video-use /path/to/video-use && pip install -e /path/to/video-use`

## Environment check one-liner

```bash
{
  echo -n "ScreenKite:  "; test -x '/Applications/ScreenKite.app/Contents/MacOS/ScreenKite' && echo OK || echo MISSING
  echo -n "node:        "; node --version 2>/dev/null || echo MISSING
  echo -n "ffmpeg:      "; ffmpeg -version 2>/dev/null | head -1 || echo MISSING
  echo -n "hyperframes: "; npx --yes hyperframes@latest --version 2>/dev/null || echo "will install on first use"
  echo -n "ELEVEN_LABS_API_KEY: "; grep -q ELEVEN_LABS_API_KEY .env 2>/dev/null && echo OK || echo MISSING
}
```

If anything prints MISSING, install it before starting the pipeline. Tell the user clearly what's missing and give them the install command above — do not try to silently work around a missing dependency.
