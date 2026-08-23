---
name: debug
description: Systematic fault isolation. Use when something fails, errors, hangs, or misbehaves and the cause is not obvious — do minimal reproduction, read the real output, check assumptions, bisect changes, and fix the cause rather than the symptom.
---

# Debug

Find the cause, not the workaround. Work in the cheapest loop that returns information.

## 1. Reproduce minimally

- Shrink the failing case: smallest input, shortest path, single config value. If it only fails with X, X is a clue.
- Capture the exact error: full stderr, exit code, log lines, not a paraphrase.

## 2. Read the real output

- Look at what the tool actually printed, not what you expected. Check stderr, logs, exit codes, and the file system effects.
- If a command has a verbose/debug flag, turn it on before asking questions.

## 3. Check assumptions in order

- Environment: right tool/version on PATH, right interpreter, right working directory, env vars set.
- Permissions and ownership.
- Paths and quoting (spaces, symlinks, case sensitivity, trailing slashes).
- Configuration: the file being read is the file you edited (check with verbose output, not vibes).

## 4. Bisect your own changes

- What changed most recently? Revert half of it and see which half keeps the failure. Prefer reverting to rewriting.

## 5. Fix the cause, then prove it

- Fix the root cause, not the visible symptom. Re-run the minimal repro to confirm, then run the related checks the change could affect.

## 6. Know when to stop

- If you're still guessing after several failed rounds, stop and report: what you tried, what you observed, and one specific question — not another random attempt.