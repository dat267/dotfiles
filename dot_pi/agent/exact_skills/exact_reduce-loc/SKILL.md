---
name: reduce-loc
description: Slim a codebase while preserving observable behavior. Finds duplication, dead code, pass-through layers, and over-general abstractions, pins the behavior with tests, then removes code in small verified and separately committed steps. Invoked explicitly, optionally with a scope or a target.
disable-model-invocation: true
---

# Reduce LOC

Fewer lines, same behavior. Line count is the measurement, not the goal: the
result must stay readable, tested, and safe to change. Never trade observable
behavior, public surface, or test coverage for a smaller diff.

Invocation arguments can narrow the scope (a path, package, or symbol) and set a
target. Honor them. Invocation is not permission to push, release, change a
public contract, or install dependencies.

## 1. Establish the baseline

- Read the workspace's agent instructions, then `ARCHITECTURE.md` for structure
  and `TODO.md` for planned work. Do not propose removing documented
  scaffolding, extension points, or work in progress as dead code.
- Record the working-tree status and current commit. Preserve existing edits;
  never reset, stash, or overwrite someone else's work.
- Run the workspace gate (lint, typecheck, test) and record pre-existing
  failures so a new one can be told apart from them.
- Measure the baseline with a reproducible command and the same scope you will
  report later. `git ls-files -z | xargs -0 wc -l`, or the project's LOC tool,
  run on first-party source. State exclusions: vendored dependencies, generated
  code, build output, lock files, snapshots.
- Ask only when the scope or target is ambiguous in a way that changes which
  code may be touched.

## 2. Find candidates

Inventory first-party production code, tests, scripts, and configuration.
Prioritize the reductions with the highest (lines saved × confidence) / risk:

- **Duplication:** copy-pasted blocks, near-duplicates that drifted, parallel
  implementations of one concept. Prefer removing duplicated *knowledge* over
  deduplicating accidental shape: two functions that look alike but change for
  different reasons should stay separate.
- **Dead weight:** unused exports, imports, flags, parameters, config keys,
  feature switches, compatibility shims, commented-out code, and branches that
  cannot be reached. Prove reachability, do not assume it.
- **Pass-through layers:** wrappers that only rename, one-caller helpers, one-
  implementation interfaces, indirection added for a test seam that no test
  uses, modules that re-export a single symbol.
- **Over-general abstractions:** generic factories, strategies, or option
  objects with one concrete user, speculative extension points with no consumer.
- **Boilerplate:** hand-rolled code the standard library or a language feature
  already provides, repeated setup that a single helper can own, long
  conditionals that guard clauses collapse.
- **Tests and docs:** redundant tests that assert the same behavior as another
  test, duplicated documentation facts. Never remove the only test covering a
  behavior, and keep the one home for each documented fact.

Keep the candidate list in your working notes: location, expected saving, proof
needed, and risk.

## 3. Define and pin behavior

Behavior is what a caller can observe: return values, errors, exit codes,
diagnostics, files and wire formats, CLI and configuration surface, documented
defaults, permissions, and ordering or timing guarantees. Internal structure is
yours to change; the surface is not.

Before cutting, make the behavior checkable:

- Find the tests that already pin the candidate. Name them.
- When coverage is missing, write a characterization test first. It must pass on
  the current code and fail on a deliberately broken variant (mutate a branch or
  change the output once to confirm it is sensitive). Removal is not new
  behavior, so the red step here proves the test can catch a loss, not that the
  code should be written.
- Use golden files or snapshots for serialized output, CLI help, and generated
  structure when the shape is easier to diff than to assert.
- Prove dead code with more than a text search: compiler or language-server
  references, unused-export warnings, coverage, dynamic import and reflection
  checks, string and configuration references, and external consumers of a
  published package. "No grep hits" is not proof.
- Check the public surface before removing it: README, reference docs, release
  notes, changelog, and open issues. A feature may be unused inside the repo and
  used by callers outside it.

Skip candidates that cannot be pinned. Record them as unverified rather than
removing them on judgment alone.

## 4. Cut in verified steps

For each candidate, in priority order:

1. Run the covering test and confirm it passes before the edit.
2. Make one coherent reduction: delete, consolidate, or simplify one thing.
   Prefer deletion over rewriting, and use the formatter so unrelated lines do
   not move.
3. Re-run the focused test, adjacent tests, and the workspace gate. If the test
   now fails, the reduction changed behavior: revert it or fix the test only if
   the original assertion was wrong, and say why.
4. Compare LOC against the baseline with the same command. If the step did not
   remove lines or reduce duplication, revert it. A step that needs more lines
   than it removes is not a reduction under this skill.
5. Commit the verified step separately, with explicit paths and the measured
   before/after or the behavior test named. Keep unrelated edits and other
   candidates out of the commit.

Do not batch independent reductions. A failed step must not leave the tree red,
and a revert must restore the previous commit state exactly.

## 5. Measure and report

- Report baseline and final LOC with the exact command and scope, and the
  percentage saved.
- List each committed step: what was removed, which test pins the behavior, and
  the verification run.
- List what was left and why: risk, external consumers, documented behavior,
  missing coverage, or a decision that belongs to the user.
- State the limits plainly: fewer lines is not automatically better, passing
  tests do not cover every path, and unmeasured areas were not reduced.

## Stop and ask

Ask before a reduction that:

- changes a public API, CLI flag, configuration key, file format, or documented
  default, even when the repository has no internal caller;
- deletes the only test for a behavior, or a test written against a bug that is
  still open;
- removes error handling, validation, logging, metrics, or a security control;
- merges modules across an ownership or platform boundary, or touches
  concurrency and lifetime logic;
- requires a new dependency, a behavior change, or a large rewrite to save a
  few lines.

## What does not count

- Golfing: dense one-liners, nested ternaries, shortened names, or removed
  whitespace that make review harder.
- Weakening types (`any`, casts, unchecked assertions) to shorten a file.
- Deleting comments that record non-obvious constraints, or docs that own a
  fact.
- Inlining a helper into many call sites, spreading knowledge instead of
  concentrating it.
- Rewriting working code in a different style with no measurable removal.
- Breaking tests apart or merging them to move lines between files.
