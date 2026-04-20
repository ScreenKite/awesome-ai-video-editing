# Hyperframes Composition Contract

Every Hyperframes composition generated as a ScreenKite B-roll MUST follow these rules. Violations produce broken renders, double-exit fades, or invisible content.

## Frame design

**1. Content fills the full 1920×1080 frame.** The MP4 IS the PiP — when ScreenKite places it at `placeSelf="topRight" width="40%"`, the whole frame lands in the corner. Content positioned in a sub-corner of the 1920×1080 will be buried in a corner-of-a-corner and look lost.

- ✅ Full-bleed warm cream background `#FFF5E8`
- ✅ Content centered or flush-laid-out with padding 80–140px from canvas edges
- ✅ Typography LARGE: display 160–220px, subtitle 72–96px, body 44–72px
- ❌ Card tucked in one quadrant of the 1920×1080 with the rest empty

**2. Typography is LARGE.** Defaults are small for good reason — most content is full-frame. For corner-PiP B-roll, content renders at 35–45% of screen width, so text needs to be readable when compressed. Display 180px → ~70px on screen at 40% width. Body 56px → ~22px. That's the floor.

## Timeline shape

**3. Entry → settled hold → NO internal exit.** Structure:

```
0.0 – 1.5s   entry animations (pop in, slide in, stagger reveal)
1.5 – end    settled hold — content fully visible, minimal ambient motion
NEVER add a fade/scale-out in the last 0.3–0.5s
```

ScreenKite's `magicMove` transition handles the exit. If the composition also animates out, viewers see a double-exit that feels broken. Leave the exit to ScreenKite.

**4. Composition duration ≥ DSL window duration + 1.5–2s reading hold.** The viewer needs time to read after entry completes. A 5s DSL window needs at least 3.5s of post-entry hold. Don't render a 4s composition for a 4s DSL window — the viewer won't have time to read.

Example sizing:

| DSL window | Minimum composition duration |
|---|---|
| 3.6s (lower-third) | 3.6s (entry 0.9s + hold 2.7s) |
| 5.0s (title card) | 5.5s (entry 1.5s + hold 4s) |
| 6.0s (product plug) | 7.0s (entry 2.0s + hold 5s) |

## Hard GSAP rules

**5. Synchronous timeline, paused, registered.**

```js
window.__timelines = window.__timelines || {};
const tl = gsap.timeline({ paused: true });
// tl.from(...), tl.to(...), etc.
window.__timelines["main"] = tl;
```

- NO `async` / `await` / `setTimeout` / `Promise` in timeline construction. The capture engine reads `window.__timelines` synchronously after DOMContentLoaded.
- NO `Math.random()`, `Date.now()`, or any non-deterministic value. Use index-based loops or seeded PRNG.
- NO `repeat: -1`. Infinite repeats break rendering. Calculate: `repeat: Math.ceil(holdLen / cycleLen) - 1`.
- Only animate visual props: `opacity`, `x`, `y`, `scale`, `rotation`, `color`, `backgroundColor`, `borderRadius`, transforms. Never `visibility`, `display`, or media `.play()`.

**6. Vary eases.** At least 3 different eases per composition to avoid robotic feel:

- `back.out(1.6)` — cards pop in
- `back.out(2.2)` — bigger pop, more bounce
- `elastic.out(1, 0.5)` — playful wobble
- `power3.out` — clean slide
- `power2.inOut` — smooth arc
- Never `linear` — looks mechanical.

**7. Offset first animation by 0.1–0.3s.** Starting at `t=0` feels abrupt.

## Structure

**8. Standalone composition — no `<template>` wrapper.** The root `<div data-composition-id="main">` goes directly inside `<body>`. `<template>` is only for sub-compositions loaded via `data-composition-src`.

**9. Required attributes on root:**

```html
<div id="root"
     data-composition-id="main"
     data-start="0"
     data-duration="5.5"
     data-width="1920"
     data-height="1080">
```

**10. `data-track-index` on timed children.** Same-track clips cannot overlap. Use separate indices (1, 2, 3, …) if clips have overlapping start/end times.

## Boilerplate

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: transparent; }
      /* your scene styles */
    </style>
  </head>
  <body>
    <div id="root"
         data-composition-id="main"
         data-start="0"
         data-duration="5.5"
         data-width="1920"
         data-height="1080">
      <!-- scene content -->
    </div>
    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      // tweens
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
```

## Lint before done

Every composition must pass `npx hyperframes lint --json` with 0 errors. Info findings are normal (e.g., CDN script notice). Warnings should be addressed but are not blocking.

## When the rules conflict

If a composition needs ambient motion during hold (e.g., logo bob, sparkle pops), keep the amplitude small (≤10–15% scale change, ≤12px y motion). The viewer is reading text — ambient motion draws the eye away. Prefer stillness after entry.
