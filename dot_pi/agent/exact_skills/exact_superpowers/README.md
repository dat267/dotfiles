# Superpowers skills for Pi

Vendored from [obra/superpowers](https://github.com/obra/superpowers) at commit
`2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` (v7.0.1, 2026-10-21).
MIT licensed; see `LICENSE` in this directory.

## Included

- `superpowers-brainstorming`
- `superpowers-writing-plans`
- `superpowers-receiving-code-review`
- `superpowers-finishing-a-development-branch`

## Adaptations

- Every skill name is prefixed with `superpowers-` so it cannot collide with
  the local `tdd`, `systematic-debugging`, `code-maintenance`, or
  `code-reduction` skills.
- Cross-skill references point at the local names.
- The upstream `using-superpowers` bootstrap skill and its Pi extension are not
  installed. They inject context at session start and require skill invocation
  before any response, which conflicts with the existing skills and the
  session's response contract.
- `writing-plans` hands execution to the local `tdd`, `systematic-debugging`,
  and `code-maintenance` skills instead of the subagent-driven workflows,
  because Pi core has no subagent tool.
- Runtime artifacts go under the OS temp directory. Plans and design specs
  live in `${TMPDIR:-/tmp}/superpowers/`, and visual-companion sessions in
  `${TMPDIR:-/tmp}/brainstorm-*`. The upstream `--project-dir` option and the
  `.superpowers/` repository writes were removed from the scripts and docs.
- Harness-specific instructions were removed. The skills assume Pi: inline
  builder checks instead of subagent dispatch, and a single launch path for the
  visual companion.
- The visual companion sends no telemetry and loads no remote branding image.
- Not vendored: `test-driven-development` and `systematic-debugging` (local
  equivalents exist), `subagent-driven-development`,
  `dispatching-parallel-agents`, `executing-plans`, `requesting-code-review`
  (subagent tool required), `diagnosing-superpowers` (maintainer diagnostics),
  and `writing-skills` (its testing method requires subagents).
- Removed after review as redundant here:
  `superpowers-verification-before-completion` (the `karpathy-guidelines` and
  `tdd` skills already require verification before a completion claim) and
  `superpowers-using-git-worktrees` (rarely applicable, and the repository's
  branch and commit policy lives in `AGENTS.md`).
