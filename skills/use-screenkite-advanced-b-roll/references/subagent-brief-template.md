# Sub-Agent Brief Template

Template for Phase 6 parallel agent prompts. Copy this, fill in the SLOT-SPECIFIC sections, and dispatch.

## Template

```
Build ONE Hyperframes composition: <one-line description>. Nothing else.

ABSOLUTE OUTPUT PATH: <BROLL_DIR>/slot_<XX>/index.html

TECHNICAL SPEC (non-negotiable):
- 1920×1080, 30fps
- Duration: <N> seconds (data-duration="<N>")
- Standalone composition: root div directly in <body>, NO <template> wrapper
- GSAP 3.14.2 from CDN (boilerplate below)
- html/body: `background: transparent`
- Scene fills with warm cream #FFF5E8 (full-bleed)
- Timeline: paused, synchronous, registered as window.__timelines["main"]
- NO Math.random, Date.now, async, setTimeout, Promise, repeat: -1
- Only animate visual props (opacity, x, y, scale, rotation, colors, transforms)

FRAME DESIGN — CRITICAL:
- This MP4 is placed as a corner PiP in ScreenKite. Content MUST fill the 1920×1080 frame.
- Do NOT position content in a sub-corner of the frame — it would be buried in a corner-of-a-corner.
- Cream full-bleed bg, content centered with padding 80–140px from edges.
- Typography LARGE: display <SIZE>px, subtitle <SIZE>px, body <SIZE>px.

TIMELINE SHAPE — CRITICAL:
- 0.0–1.5s: entry animations
- 1.5–<N>s: settled hold, minimal ambient motion
- NO internal exit animation in the last 0.3–0.5s — ScreenKite handles exit via magicMove
- All ambient repeats finite: `repeat: Math.ceil(holdLen / cycleLen) - 1`
- Vary eases: at least 3 different (back.out, elastic.out, power3.out, etc.). Never linear.

CONTENT:
- <SLOT-SPECIFIC: exact text, icons, emojis, layout>
- <SLOT-SPECIFIC: main title "XXX" — 220px Inter weight 900, color #2B1A13>
- <SLOT-SPECIFIC: subtitle "中文字幕" — 96px PingFang SC weight 700>
- <SLOT-SPECIFIC: additional elements — chips, badges, decorative dots, sparkles>

PALETTE (exact hex):
- Canvas: #FFF5E8 (cream)
- Card: #FFFFFF
- Shadow: rgba(217, 119, 87, 0.18)
- Anthropic orange: #D97757
- Coral: #FF8B65
- Peach: #FFBF9B
- Sky: #7FB5D0
- Mint: #9FD7B8
- Lavender: #B9A6E6
- Lemon: #FFD872
- Text dark: #2B1A13
- Text muted: #8A6B5A

TYPOGRAPHY:
- Chinese: font-family: 'PingFang SC', 'Heiti SC', system-ui, sans-serif; weight 700
- English display: font-family: 'Inter', 'SF Pro Display', system-ui, sans-serif; weight 900
- Mono: font-family: 'SF Mono', Menlo, monospace

ANIMATION TIMELINE (total <N>s):
- 0.0–0.4s: <first element> entry — <ease>, <tween>
- 0.3–0.8s: <second element> entry with stagger
- 0.8–1.5s: <remaining elements> stagger with varied eases
- 1.5–<hold-end>s: HOLD. Minimal ambient (if any):
  - <element> gentle bob/wobble with finite yoyo
  - <element> soft glow/pulse with finite repeat
  (keep amplitude small; the viewer is reading)
- DO NOT animate anything out at the end. Final frame = fully settled state.

ASSETS (if applicable):
- <SLOT-SPECIFIC: image path, e.g., assets/logo.png at 320×320>
- <SLOT-SPECIFIC: SVG icons inline or as dataURI>

LAYOUT:
- <SLOT-SPECIFIC: CSS flex column / grid / absolute positioning>

TASKS:
1. Write full index.html at the absolute path above.
2. cd into the slot directory and run `npx hyperframes lint --json 2>&1`. Fix errors. Warnings OK unless contrast-related.
3. Report: file size (bytes), lint status (errors/warnings count), any notes.

DO NOT ask questions. If anything is ambiguous, pick the warmest/cutest/most-legible interpretation and proceed.

BOILERPLATE:

<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: transparent; }
      /* scene styles */
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="<N>" data-width="1920" data-height="1080">
      <!-- scene content -->
    </div>
    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      // tl.from(...) / tl.to(...)
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
```

## Dispatch pattern

Launch all N agents in ONE message with N Agent tool calls, each `run_in_background: true`. Each brief is self-contained; agents do not share context with each other or the parent.

## Reading hold math

To decide composition duration:

- DSL display window = `W` seconds
- Entry budget = ~1.5s
- Reading hold needed = ≥ 1.5-2s
- **Composition duration ≥ W + 0.5s** (slight safety margin so the last settled frame is captured before magicMove kicks in)

Examples:
- Lower-third (3.6s DSL) → composition 3.6s (entry 0.9s + hold 2.7s)
- Title card (5.0s DSL) → composition 5.5s (entry 1.5s + hold 4s)
- Complex graph (5.0s DSL) → composition 6.0s (entry 2.0s + hold 4s)

## Common slot recipes

### Lower-third nameplate
- Card bottom-left of frame (since DSL places whole PiP at bottomLeft, card ends up bottom-left of screen)
- Name 180–220px Inter 900
- Handle/URL 48–56px mono
- Accent dot or underline in orange

### Title reveal card
- White rounded card centered (radius 72px)
- Top badge (orange pill with date/source)
- Huge display title 180–220px
- Chinese subtitle 72–96px
- Decorative dots/wedges/sparkles at corners of card

### Comparison card
- Two cards side-by-side (gap 60–80px)
- Equal size, different border colors (peach vs orange)
- Emoji/icon at top of each
- Title + 3 feature chips
- "vs" ornament centered between

### Connector diagram
- 2-3 input nodes on left
- Curved arrows drawing in via strokeDashoffset
- Output node on right (highlighted with orange border)
- Small privacy/safety pill badge

### Quota / split card
- Two stacked horizontal bars, different fill colors
- Animated percent via proxy-tween onUpdate
- "互不影响" badge below
- Minimal ambient motion

### Product plug
- Big logo image at top (200–320px, rounded 72px, warm glow shadow)
- Display title 140–180px
- Tagline 60–80px orange
- 3 feature chips
- CTA arrow pulsing down

### Tool-use node graph
- Center node with orbiting satellites
- Curved SVG paths connecting
- Traveling dots along paths (deterministic, not random)
- Analogy caption at bottom

See `references/visual-ideas-menu.md` for the full catalog.
