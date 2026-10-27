# Status

## Current state

Working tree clean on `main`, two local commits ahead of `origin/main`: the `documentation` rename and this doc audit. The Pi config is deployed, including `APPEND_SYSTEM.md` and the renamed `documentation` skill, but the audit's `exact_py/AGENTS.md` fix is not: `~/.local/scripts/py/AGENTS.md` is behind source until the next apply. Pi settings select the `system` theme with `flat` installed as an option, and all five skills are deployed.

## Verified

- `python3 -m unittest discover -s exact_tests` from `dot_local/scripts/exact_py/`: 713 tests, all pass (11 skipped).
- `pi_lint_extensions.py --root "$PWD"`: six extension directories pass `tsc --strict` (`--root .` fails with `TS6053` because the linter resolves files from the root it is given).
- No dangling symlinks anywhere in the tree, so `chezmoi execute-template` renders from the repo source again.
- Five skill directories under `dot_pi/agent/exact_skills`, each `SKILL.md` frontmatter `name` matching its directory (`code-review`, `documentation`, `karpathy-guidelines`, `systematic-debugging`, `tdd`), and the deployed skills identical to source.
- `chezmoi status` shows only the pending `~/.local/scripts/py/AGENTS.md` update; the deployed `APPEND_SYSTEM.md` and `documentation/SKILL.md` are identical to source.

## Completed

- Doc audit against the code: corrected the deploy state and skill verification in `STATUS.md`, the `chezmoi status` claim in `TODO.md`, the stale Visual Studio snippets claim in `README.md`, the Windows CI description and command block in `AGENTS.md`, and the stale path and `expectedFailure` convention in `dot_local/scripts/exact_py/AGENTS.md`.

- `doc-maintenance` renamed to `documentation` across the directory, frontmatter name, and heading, with references updated in `APPEND_SYSTEM.md` and the project docs.

- `APPEND_SYSTEM.md` no longer restates the document ownership rules; it keeps the five file names, the read-before-planning trigger, the update-in-the-same-work habit, and a pointer to `documentation`, which is now the only place those rules live.

- `documentation` now owns the five-document convention, including the shapes to create them, and the separate `project-docs` skill is gone.

- Stale `@earendil-works/chord` symlinks from a removed Pi release are gone, and `pi_lint_extensions` now prunes dangling links instead of leaving them for the next tool that walks the tree.
- Five project documents introduced (this file set), with an always-on summary in `dot_pi/agent/APPEND_SYSTEM.md` and the shapes and audit in the `documentation` skill.
- Skills made portable: no Pi-only invocation syntax, Git steps conditional with non-Git fallbacks, `tdd` covers more stacks and repos without a harness, cross-skill handoffs optional.
- `code-review` replaced `improve-codebase-architecture`, and its coverage ledger was removed.
- Pi `flat` theme added; `system` kept as the default.
- Konsole One Dark and One Light color schemes added next to the existing profile.
- Pi goal extension disabled through a settings exclusion, keeping its source and tests.
- `documentation` rewritten to audit against the current code rather than commit history, covering the five files first and then any other doc found.

## Blockers

None.

## Next action

Run `git push` (yours to run), apply the pending doc update (`chezmoi apply --force ~/.local/scripts/py/AGENTS.md`, yours to run), then take the only `TODO.md` Now item: confirm the `mimeapps.list` behavior on a real full apply.
