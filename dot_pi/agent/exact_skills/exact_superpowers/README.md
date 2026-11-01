# Superpowers skills for Pi

Vendored from [obra/superpowers](https://github.com/obra/superpowers) at commit
`2ce8aa15d05bd57213e6f746f953aafb7ded7a8b` (v7.0.1, 2026-10-21).
MIT licensed; see `LICENSE` in this directory.

## Included

- `superpowers-brainstorming`
- `superpowers-writing-plans`
- `superpowers-verification-before-completion`
- `superpowers-receiving-code-review`
- `superpowers-finishing-a-development-branch`
- `superpowers-using-git-worktrees`

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
- Not vendored: `test-driven-development` and `systematic-debugging` (local
  equivalents exist), `subagent-driven-development`,
  `dispatching-parallel-agents`, `executing-plans`, `requesting-code-review`
  (subagent tool required), `diagnosing-superpowers` (maintainer diagnostics),
  and `writing-skills` (its testing method requires subagents).
