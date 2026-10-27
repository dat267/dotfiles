# Progress

## Current state

Working tree clean on `main`, three local commits ahead of `origin/main` (the project-documentation work). Everything managed by chezmoi is deployed: Pi settings select the `system` theme with `flat` installed as an option, the six skills load without warnings, and `~/.pi/agent/APPEND_SYSTEM.md` carries the project-document section. `chezmoi apply --dry-run` reports nothing pending.

## Verified

- `python3 -m unittest discover -s exact_tests` from `dot_local/scripts/exact_py/`: 710 tests, 6 errors, all in `test_lifecycle_hooks` and all caused by the broken `chord` symlink.
- Pi's own skill loader over `dot_pi/agent/exact_skills`: six skills, zero warnings.
- `chezmoi apply --dry-run`: no output, so no pending changes.

## Completed

- Five project documents introduced (this file set), with an always-on summary in `dot_pi/agent/APPEND_SYSTEM.md` and structure, templates, and audit steps in the `project-docs` skill.
- Skills made portable: no Pi-only invocation syntax, Git steps conditional with non-Git fallbacks, `tdd` covers more stacks and repos without a harness, cross-skill handoffs optional.
- `code-review` replaced `improve-codebase-architecture`, and its coverage ledger was removed.
- Pi `flat` theme added; `system` kept as the default.
- Konsole One Dark and One Light color schemes added next to the existing profile.
- Pi goal extension disabled through a settings exclusion, keeping its source and tests.
- `doc-maintenance` rewritten to audit against the current code rather than commit history, covering the five files first and then any other doc found.

## Blockers

- The `@earendil-works/chord` symlink under `exact_auto-default/node_modules` points at a removed release. It keeps six lifecycle tests red and breaks template rendering when the source directory is the repo.

## Next steps

1. Push the three local commits.
2. Fix the broken symlink, then re-run `test_lifecycle_hooks`.
3. Confirm the `mimeapps.list` behavior on a real full apply and record the outcome here.
