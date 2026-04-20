# DSL Cookbook

Ready-to-copy ScreenKite advanced layout DSL snippets, plus the plan.json schema for `scripts/apply_broll_dsl.py`.

## Table of contents

- [DSL anatomy](#dsl-anatomy)
- [Placement recipes](#placement-recipes)
- [plan.json schema](#planjson-schema)
- [Raw CLI call examples](#raw-cli-call-examples)
- [Inspecting the project](#inspecting-the-project)

## DSL anatomy

The advanced layout DSL is TSX-like XML that ScreenKite parses. Every scene is a `<SceneLayout>` with a root `<ZStack>` that holds three layer primitives:

```xml
<SceneLayout version="2">
  <ZStack alignment="bottomRight">
    <ScreenKite.MainScreen />
    <ScreenKite.Camera  width="22%" aspect="3:4" placeSelf="bottomRight" />
    <ScreenKite.Visual  width="40%" aspect="16:9" placeSelf="topRight"
                        contentMode="fit"
                        source="/abs/path/slot_XX.mp4" />
  </ZStack>
</SceneLayout>
```

- `ScreenKite.MainScreen` fills the canvas (the screen recording).
- `ScreenKite.Camera` is the host camera PiP.
- `ScreenKite.Visual` is the B-roll MP4 placed as a corner PiP.

### `placeSelf` values

`topLeft`, `top`, `topRight`, `left`, `center`, `right`, `bottomLeft`, `bottom`, `bottomRight`.

### `width` and `aspect`

`width` is a percentage of canvas width. `aspect` is `W:H` (e.g. `"16:9"`, `"3:4"`, `"1:1"`). For B-roll rendered at 1920×1080, always use `aspect="16:9"`.

### `contentMode`

- `fit` — letterbox if needed; never crop
- `fill` — crop if needed; never letterbox

Use `fit` for B-roll; content is designed to fill the frame so letterboxing is rarely triggered.

## Placement recipes

### Lower-third (intro nameplate)

Host camera stays bottomRight; the lower-third sits bottomLeft so they don't collide.

```xml
<SceneLayout version="2">
  <ZStack alignment="bottomRight">
    <ScreenKite.MainScreen />
    <ScreenKite.Camera  width="22%" aspect="3:4" placeSelf="bottomRight" />
    <ScreenKite.Visual  width="40%" aspect="16:9" placeSelf="bottomLeft"
                        contentMode="fit" source="{ABSOLUTE_SLOT01_PATH}" />
  </ZStack>
</SceneLayout>
```

### Top-right explainer (most common)

```xml
<SceneLayout version="2">
  <ZStack alignment="bottomRight">
    <ScreenKite.MainScreen />
    <ScreenKite.Camera  width="22%" aspect="3:4" placeSelf="bottomRight" />
    <ScreenKite.Visual  width="42%" aspect="16:9" placeSelf="topRight"
                        contentMode="fit" source="{ABSOLUTE_SLOT_PATH}" />
  </ZStack>
</SceneLayout>
```

### Top-left (alternates with top-right for rhythm)

```xml
<SceneLayout version="2">
  <ZStack alignment="bottomRight">
    <ScreenKite.MainScreen />
    <ScreenKite.Camera  width="22%" aspect="3:4" placeSelf="bottomRight" />
    <ScreenKite.Visual  width="40%" aspect="16:9" placeSelf="topLeft"
                        contentMode="fit" source="{ABSOLUTE_SLOT_PATH}" />
  </ZStack>
</SceneLayout>
```

### Width guidelines

| Content type | Width |
|---|---|
| Single-word/short nameplate | 30–38% |
| Title card / comparison | 40–45% |
| Diagram / graph | 42–48% |
| Full chart | 48–55% (uncommon) |

Wider than 55% starts to fight the main screen. Keep it tight.

## plan.json schema

Consumed by `scripts/apply_broll_dsl.py`. Minimal example:

```json
{
  "broll_dir": "/abs/path/to/broll",
  "camera": {
    "width": "22%",
    "aspect": "3:4",
    "placeSelf": "bottomRight"
  },
  "transition": "magicMove",
  "slots": [
    {
      "num": "01",
      "start": 1.4,
      "duration": 3.6,
      "placeSelf": "bottomLeft",
      "width": "40%",
      "aspect": "16:9",
      "contentMode": "fit"
    },
    {
      "num": "02",
      "start": 5.5,
      "duration": 5.0,
      "placeSelf": "topRight",
      "width": "42%"
    }
  ]
}
```

Per-slot optional fields (inherit defaults if omitted): `aspect` ("16:9"), `contentMode` ("fit"), `transition` (from top-level).

Source path resolution: `<broll_dir>/slot_<num>/renders/slot_<num>.mp4`.

## Raw CLI call examples

If you need to call `setSceneLayout` directly without `apply_broll_dsl.py`:

```bash
cat > /tmp/sk.json <<'EOF'
{
  "start": 5.5,
  "end": 10.5,
  "transition": "magicMove",
  "dslSource": "<SceneLayout version=\"2\"><ZStack alignment=\"bottomRight\"><ScreenKite.MainScreen /><ScreenKite.Camera width=\"22%\" aspect=\"3:4\" placeSelf=\"bottomRight\" /><ScreenKite.Visual width=\"42%\" aspect=\"16:9\" placeSelf=\"topRight\" contentMode=\"fit\" source=\"/abs/path/slot_02.mp4\" /></ZStack></SceneLayout>"
}
EOF

'/Applications/ScreenKite.app/Contents/MacOS/ScreenKite' agent tool call \
  --name setSceneLayout --input-file /tmp/sk.json --json
```

Clearing a range back to default PiP:

```bash
cat > /tmp/sk_clear.json <<'EOF'
{ "start": 10.5, "end": 17.9, "mode": "pictureInPicture", "transition": "magicMove" }
EOF

'/Applications/ScreenKite.app/Contents/MacOS/ScreenKite' agent tool call \
  --name setSceneLayout --input-file /tmp/sk_clear.json --json
```

### Dry-run first

Set `"dryRun": true` in the payload to get the resolved surface geometry without mutating the project. Useful for sanity-checking placement and collision with the camera before committing.

## Inspecting the project

```bash
# Segments on the scene-layout track
'/Applications/ScreenKite.app/Contents/MacOS/ScreenKite' agent tool call \
  --name getProjectState --input-json '{"scope":"layout"}' --json | \
  python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"{s['start']:6.2f}→{s['end']:6.2f}s  {s['mode']}\") for s in d['layout']['segments']]"
```

After applying the plan, verify:

- Exactly N `advanced` segments at the expected ranges
- Every gap between them is `pictureInPicture` (the default)
- No `advanced` tails leftover from a prior, longer plan

If tails exist, `apply_broll_dsl.py` will clear them on next run; or call `setSceneLayout` with `mode: "pictureInPicture"` manually over each tail range.
