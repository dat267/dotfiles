---
name: tdd
description: Test-driven development workflow. Write a failing test first, then the minimal implementation, then refactor. Use when implementing a new feature, fixing a bug, changing behavior, or adding test coverage in any codebase.
---

# Test-Driven Development

The invariant: **no production code exists without a failing test that demands it.**

## The loop

1. **Red** — write ONE test describing the next smallest behavior. Run it. It must fail for the expected reason (assertion failure, not a typo or import error).
2. **Green** — write the smallest code that passes. Resist generalizing early.
3. **Refactor** — with all tests green, remove duplication and improve names. Tests stay untouched unless the behavior contract changed.
4. Repeat.

## Rules

- Never write implementation before the failing test — not even "obvious" code.
- One behavioral change per test. If you need "and" in the test name, split it.
- Run the tests after every step. Never batch red→green across multiple tests.
- A bug fix starts with a test that **reproduces the bug** first, proves it fails, then gets fixed. The test name describes the bug's behavior, not the fix.
- If a test is hard to write, the design is wrong — say so and propose the seam instead of testing private internals or mocking heavily.
- Do not weaken an assertion to make a test pass. If the assertion was wrong, change it deliberately and say why.
- Do not delete or skip a failing test. Fix the code or fix the test's contract explicitly.

## Test conventions

Match the repo's existing conventions first. Defaults when none exist:

- Node/TypeScript: `node --test` (no test runner dependencies)
- Python: `unittest` (stdlib only)
- Tests live beside the code as `<name>.test.ts` / `test_<name>.py`, or in `tests/` — follow the repo
- Pure logic gets direct tests; I/O and side effects get mocked at the boundary

## When NOT to apply the full loop

State it explicitly, then proceed without it:

- Trivial config/renames where no behavior exists to test
- Exploratory spikes — but throwaway code must either get tests before landing or be deleted

## Stopping

Done means: all tests green, run command and its output shown, no skipped or weakened assertions. If some test is still red, the task is not done — say which and why.
