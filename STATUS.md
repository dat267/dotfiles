# Status

## Current state

Working tree clean on `main`, five local commits ahead of `origin/main`: the `documentation` rename, the doc audit, the clarity rewrite, the correctness-and-evidence rewrite, and the removal of the appended prompt and documentation skill. The source has no `APPEND_SYSTEM.md` and four skills; the deployed config still has the old appended prompt and the `documentation` skill until the removal is applied. Pi settings select the `system` theme with `flat` installed as an option.

## Verified

- `python3 -m unittest discover -s exact_tests` from `dot_local/scripts/exact_py/`: 713 tests, all pass (11 skipped).
- `pi_lint_extensions.py --root "$PWD"`: six extension directories pass `tsc --strict` (`--root .` fails with `TS6053` because the linter resolves files from the root it is given).
- No dangling symlinks anywhere in the tree, so `chezmoi execute-template` renders from the repo source again.
- Four skill directories under `dot_pi/agent/exact_skills` (`code-review`, `karpathy-guidelines`, `systematic-debugging`, `tdd`); their deployed copies are identical to source.
- `chezmoi status` shows the pending `.pi/agent/skills/documentation` deletion and `~/.local/scripts/py/AGENTS.md` update, plus a pre-existing `~/.pi/agent/settings.json` difference (`hideThinkingBlock` is `false` in the deployed file and `true` in the template). The deployed `APPEND_SYSTEM.md` is no longer managed once its source is gone, so it needs a manual removal.

## Completed

- Removed `APPEND_SYSTEM.md` and the `documentation` skill, so Pi starts from its built-in prompt and the four remaining skills; the five project documents stay as the repo convention.

- `APPEND_SYSTEM.md` now ranks correctness and evidence first, then safety and honest uncertainty, then clarity and conciseness; every claim must cite a command and its output, a file and its lines, a direct quote, or a stated reason.

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

Run `git push` (yours to run), remove the deployed prompt and skill (`rm ~/.pi/agent/APPEND_SYSTEM.md` and `rm -rf ~/.pi/agent/skills/documentation`, yours to run), apply the pending doc update (`chezmoi apply --force ~/.local/scripts/py/AGENTS.md`, yours to run), then take the only `TODO.md` Now item: confirm the `mimeapps.list` behavior on a real full apply.
