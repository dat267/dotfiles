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
- Work in **vertical slices**: one test → one implementation → repeat. Never write all tests first, then all implementation — bulk tests verify imagined behavior.
- Run the tests after every step. Never batch red→green across multiple tests.
- A bug fix starts with a test that **reproduces the bug** first, proves it fails, then gets fixed. The test name describes the bug's behavior, not the fix.
- If a test is hard to write, the design is wrong — say so and propose the seam instead of testing private internals or mocking heavily.
- Do not weaken an assertion to make a test pass. If the assertion was wrong, change it deliberately and say why.
- Do not delete or skip a failing test. Fix the code or fix the test's contract explicitly.

## What a good test is

Tests verify **behavior through public interfaces**, not implementation details. A good test reads like a specification — "user can checkout with a valid cart" — and survives refactors because it ignores internal structure.

**Name the seam before writing the test**: the public boundary where behavior is observable without reaching inside. When choosing is non-obvious, state the seam and confirm it with the user before writing any test.

## Anti-patterns

- **Implementation-coupled**: mocks internal collaborators, tests private methods, or verifies through a side channel (querying the database instead of using the interface). The tell: the test breaks when you refactor but behavior hasn't changed.
- **Tautological**: the assertion recomputes the expected value the way the code does (`expect(add(a, b)).toBe(a + b)`), so it passes by construction and can never disagree with the code. Expected values come from an independent source of truth: a known-good literal, a worked example, the spec.
- **Horizontal slicing**: see the rules above — one tracer-bullet slice at a time.

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
