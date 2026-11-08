---
name: tdd
description: Test-driven development. Required for any feature, bug fix, or behavior change in any repo, so no production code exists without a failing test that demands it. Config, docs, and renames with no testable behavior are exempt.
---

# Test-Driven Development

The invariant: **no production code exists without a failing test that demands it.**

## The loop

1. **Red:** write ONE test for the next smallest behavior and run it. It must
   fail for the expected reason: an assertion failure, not a typo or an import
   error.
2. **Green:** write the smallest code that makes it pass. Do not generalize
   yet.
3. **Refactor:** with every test green, remove duplication and improve names.
   Leave the tests alone unless the behavior contract changed.
4. Repeat.

## Rules

- Never write implementation before its failing test, not even "obvious" code.
- One behavior per test. If the test name needs "and", split it.
- Work in **vertical slices**: one test, then its implementation, then the
  next test. Never write all the tests first and all the code after; tests
  written in bulk verify imagined behavior.
- Run the tests after every step. Never batch red-to-green across several
  tests.
- A bug fix starts with a test that **reproduces the bug** and is seen to fail
  before the fix. Name the test after the bug's behavior, not after the fix.
- When a test is hard to write, look for the public test seam before proposing
  design changes. Difficulty is not proof of bad design, and it is no reason to
  reach for private internals or heavy mocking.
- Never weaken an assertion to make a test pass. If the assertion was wrong,
  change it deliberately and say why.
- Never delete or skip a failing test. Fix the code, or change the test's
  contract explicitly.

## What a good test is

A good test verifies **behavior through public interfaces**, not implementation
details. It reads like a specification ("user can check out with a valid cart")
and survives refactors because it ignores internal structure.

**Name the seam before writing the test:** the public boundary where the
behavior can be observed without reaching inside. Ask for confirmation only
when the choice of seam changes the scope or the behavior contract.

## Anti-patterns

- **Implementation-coupled:** the test mocks internal collaborators, calls
  private methods, or checks a side channel (querying the database instead of
  using the interface). The tell: it breaks under a refactor that left behavior
  unchanged.
- **Tautological:** the assertion recomputes the expected value the way the
  code does (`expect(add(a, b)).toBe(a + b)`), so it passes by construction and
  can never disagree with the code. Take expected values from an independent
  source: a known-good literal, a worked example, the spec.
- **Horizontal slicing:** writing tests in bulk ahead of the code. See the
  rules above.

## Test conventions

Follow the repo's existing runner, file naming, and directory layout first.
Use these defaults only when the repo has none:

- JavaScript/TypeScript: `node --test` (no test-runner dependencies)
- Python: `unittest` (standard library only)
- Go: `go test ./...`
- Rust: `cargo test`
- Ruby: `ruby -Itest`, or the repo's existing Rake task
- Other stacks: the language's own runner (`mix test`, `dotnet test`,
  `swift test`)
- Put tests beside the code as `<name>.test.ts` or `test_<name>.py`, or in the
  test directory the repo already uses.
- Test pure logic directly; mock I/O and side effects at the boundary.

## When no harness exists

A repo without test infrastructure is no license to skip verification, but the
loop cannot run there as written. Pick one option and say which:

- Add the smallest harness the stack supports (one test file, the built-in
  runner), then follow the loop. This is the default for code changes.
- Verify with a reproducible check that would fail if the behavior broke: a
  script asserting exit code and output, a golden-file comparison, a query
  against a fixture. Show the command and its output, and say what it does not
  cover.
- If neither is possible, report the change as unverified instead of claiming
  it works.

## When the full loop does not apply

These skip the loop. Mention the exemption only when it explains how you
verified the change:

- Config, documentation, and renames with no testable behavior.
- Exploratory spikes. Throwaway code must get tests before it lands, or be
  deleted.

## Stopping

Done means every relevant test is green, with no skipped or weakened
assertions. If a relevant test is red or cannot run, say which one and why. If
the stack has no tests and you used a substitute check, report that check and
what it does not cover.
