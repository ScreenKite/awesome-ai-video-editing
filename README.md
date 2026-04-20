# awesome-ai-video-editing

A collection of Claude Code agent skills for AI-assisted video editing workflows.

## Skills

### [`use-screenkite-advanced-b-roll`](skills/use-screenkite-advanced-b-roll/)

End-to-end pipeline for adding short animated B-roll overlays to a
[ScreenKite](https://screenkite.com) screen recording using the advanced DSL
scene layout. Transcribes microphone audio with ElevenLabs Scribe, proofreads
product names via web search, plans brief corner-PiP visual moments, generates
each visual with [Hyperframes](https://github.com/heygen-com/hyperframes)
(HTML + GSAP) via parallel sub-agents, renders to MP4, and composites via
ScreenKite's `setSceneLayout` with `magicMove` transitions.

**Use when:** you have a ScreenKite `.skbundle` and want animated B-roll
accents layered on top of the screen + camera composition.

See [`skills/use-screenkite-advanced-b-roll/SKILL.md`](skills/use-screenkite-advanced-b-roll/SKILL.md)
for the full pipeline.

## Installation

Skills are designed for [Claude Code](https://claude.com/product/claude-code).
To use a skill, symlink (or copy) it into your Claude Code skills directory:

```bash
# Global (available in all projects)
ln -s "$(pwd)/skills/use-screenkite-advanced-b-roll" \
      ~/.claude/skills/use-screenkite-advanced-b-roll

# Or per-project
mkdir -p .claude/skills
ln -s "$(pwd)/skills/use-screenkite-advanced-b-roll" \
      .claude/skills/use-screenkite-advanced-b-roll
```

Claude Code will auto-discover the skill and invoke it when the user's request
matches its `description`.

## Prerequisites

Each skill documents its own prerequisites. For `use-screenkite-advanced-b-roll`:

- macOS with [ScreenKite.app](https://screenkite.com)
- Node.js ≥ 22 and FFmpeg
- [Hyperframes CLI](https://github.com/heygen-com/hyperframes) (auto-installs via `npx`)
- [ElevenLabs](https://elevenlabs.io) API key for Scribe transcription
- Python 3 with `requests` (`pip install requests`)

See [`skills/use-screenkite-advanced-b-roll/references/external-tools.md`](skills/use-screenkite-advanced-b-roll/references/external-tools.md)
for the full environment check.

## Contributing

Issues and PRs welcome. New skills should follow the
[skill-creator](https://github.com/anthropics/skills) convention: a `SKILL.md`
with YAML frontmatter (`name`, `description`), plus optional `references/`,
`scripts/`, and `assets/` subdirectories.

## License

[MIT](LICENSE) © 2026 Mike Chong (RockieStar Inc.)
