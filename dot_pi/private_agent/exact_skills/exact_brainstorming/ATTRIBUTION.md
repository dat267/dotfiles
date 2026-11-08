# Brainstorming skill attribution

`SKILL.md`, `visual-companion.md`, and `scripts/` come from
[obra/superpowers](https://github.com/obra/superpowers) at commit
`2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` (v7.0.1, 2026-10-21), MIT licensed;
see `LICENSE` in this directory.

Changes made for standalone use in Pi:

- Renamed from `superpowers-brainstorming` to `brainstorming`; the other
  vendored skills (writing plans, receiving code review, finishing a
  development branch, verification before completion, git worktrees) were
  removed rather than kept alongside it.
- The handoff after design approval points at planning the work and building it
  one verified step at a time, instead of invoking another skill.
- Design specs go to `${TMPDIR:-/tmp}/brainstorm/specs/`, and visual-companion
  sessions to `${TMPDIR:-/tmp}/brainstorm-*`. The upstream `--project-dir`
  option and the `.superpowers/` repository writes were removed.
- The builder check is an inline self-review: Pi core has no subagent tool, so
  `builder-check-prompt.md` was dropped.
- The description is narrowed to open-ended or explicitly requested design
  work, so clear, specified tasks no longer load the skill.
- Harness-specific instructions and the visual companion's telemetry, remote
  branding image, and per-harness launch sections were removed.
