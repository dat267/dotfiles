# Status

## Current state

Working tree clean on `main`, in sync with `origin/main` after the project-documentation work, the symlink cleanup, and the TODO/STATUS split. Everything managed by chezmoi is deployed: Pi settings select the `system` theme with `flat` installed as an option, the six skills load without warnings, and `~/.pi/agent/APPEND_SYSTEM.md` carries the project-document section. `chezmoi apply --dry-run` reports nothing pending.

## Verified

- `python3 -m unittest discover -s exact_tests` from `dot_local/scripts/exact_py/`: 713 tests, all pass.
- `pi_lint_extensions --root <repo>`: all six extension directories pass `tsc --strict`.
- No dangling symlinks anywhere in the tree, so `chezmoi execute-template` renders from the repo source again.
- Pi's own skill loader over `dot_pi/agent/exact_skills`: six skills, zero warnings.
- `chezmoi apply --dry-run`: no output, so no pending changes.

## Completed

- Stale `@earendil-works/chord` symlinks from a removed Pi release are gone, and `pi_lint_extensions` now prunes dangling links instead of leaving them for the next tool that walks the tree.
- Five project documents introduced (this file set), with an always-on summary in `dot_pi/agent/APPEND_SYSTEM.md` and structure, templates, and audit steps in the `project-docs` skill.
- Skills made portable: no Pi-only invocation syntax, Git steps conditional with non-Git fallbacks, `tdd` covers more stacks and repos without a harness, cross-skill handoffs optional.
- `code-review` replaced `improve-codebase-architecture`, and its coverage ledger was removed.
- Pi `flat` theme added; `system` kept as the default.
- Konsole One Dark and One Light color schemes added next to the existing profile.
- Pi goal extension disabled through a settings exclusion, keeping its source and tests.
- `doc-maintenance` rewritten to audit against the current code rather than commit history, covering the five files first and then any other doc found.

## Blockers

None.

## Next action

Take the only `TODO.md` Now item: confirm the `mimeapps.list` behavior on a real full apply.
