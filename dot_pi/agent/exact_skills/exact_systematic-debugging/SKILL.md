---
name: systematic-debugging
description: Root-cause debugging discipline for bugs that resist the first look. Build a red-capable feedback loop, trace the bad value to its source, and fix there. Use when something is broken, throwing, failing, flaky, slow, or sitting in a multi-layer system, and the cause is not already obvious.
---

# Systematic Debugging

Find the root cause before attempting any fix. A symptom fix is a failure even when it silences the symptom.

Exit early when the fix is obvious (a typo, a config line, a reverted commit). This skill is for bugs that resist the first look.

## Redact

Redact every secret as `<REDACTED>` in commands, outputs, and captured artifacts. Keep credentials in environment variables.
Report verification commands, pass/fail, and the shortest decisive output, not full logs.
Use a writable platform temporary directory (`$TMPDIR`, or the platform temp API); never assume `/tmp` exists.
When redacted output cannot diagnose the bug, say so and ask.

## Phase 1: Build a feedback loop

Build a tight pass/fail signal for the user's bug. Use it to evaluate bisection, hypotheses, and instrumentation.
Prioritize reproduction without repeating unproductive probes. Bound network calls, suspected hangs, and loops with explicit timeouts and iteration limits.

Construct one, in roughly this order:

1. Failing test at any seam reaching the bug: unit, integration, e2e.
2. CLI invocation with a fixture input, diffing stdout against a snapshot.
3. Curl or HTTP script against a running server.
4. Replay a captured trace (request, payload, event log) through the code path.
5. Throwaway harness in the platform temporary directory exercising the bug path in one call.
6. Property or fuzz loop: 1000 random inputs for "sometimes wrong".
7. Bisection harness driven by `git bisect run`.
8. Differential loop: same input through old vs new, diff the outputs.
9. User-relay loop for machines you cannot touch: hand the user one exact command, take back the redacted output.

Tighten it: faster (cache setup), sharper (assert the exact symptom), more deterministic (pin time, seed RNG, freeze network). A 2-second deterministic loop beats a 30-second flaky one.

Flaky bugs: raise the reproduction rate with bounded repetitions, stress, and narrower timing windows.
Record the observed failure rate. Do not require a fixed rate to proceed; report limits on confidence.

**Gate.** Phase 1 ends when you can name one command you already ran, with its invocation and redacted output shown, that is:

- [ ] Red-capable: drives the bug path and asserts the user's exact symptom.
- [ ] Deterministic: same verdict every run (flaky: a pinned high rate).
- [ ] Fast: seconds, not minutes.
- [ ] Runnable unattended, or via a user-relay loop with predictable turnaround.

Inspect targeted code, configuration, and logs while building the loop. Label preliminary hypotheses as unverified.
Do not apply a speculative fix before reproduction or a decisive diagnostic check.
If no loop is possible, report attempts and ask for environment access, a redacted artifact, or instrumentation permission.

## Phase 2: Reproduce and minimise

Run the loop. Watch it go red.

- [ ] The failure is the user's symptom, not a nearby different one.
- [ ] Reproducible across runs, or at the pinned high rate.
- [ ] The exact symptom is captured (error text, wrong output, timing).

Minimise: cut inputs, callers, config, data, and steps one at a time, re-running after each cut. Keep only what is load-bearing. Done when removing any remaining element turns the loop green. The minimal repro becomes the regression test.

## Phase 3: Trace to the source

Trace evidence toward the origin. Keep hypotheses unverified until a diagnostic check supports them.

Find working examples of the same behavior and list every difference, however small. Read reference implementations completely; never skim. Check dependencies, config, and assumptions.

Trace the bad value backward: where did it originate, and what called this with it? Keep tracing up until you reach the source. Fix at the source, never at the symptom.

Multi-layer systems (CI to build to signing, API to service to database): instrument each component boundary before proposing fixes. Log what enters and exits every layer, and verify environment and config propagation. Run once to see where it breaks, then investigate that layer.

Recent changes are prime suspects. Check `git log`, `git diff`, new dependencies, and config or environment drift.

## Phase 4: Hypothesise and test

Generate only evidence-supported, falsifiable hypotheses. Rank alternatives when multiple explanations fit; never invent candidates to meet a quota.

Give each hypothesis a testable prediction. Discard or sharpen any hypothesis without one.

Share hypotheses only when user input or approval affects the next probe. Otherwise, test without routine narration.

Then change one variable at a time, mapping each probe to one prediction.

- Prefer direct inspection (REPL, `python -m pdb`, `node --inspect`) over logging. One breakpoint beats ten logs.
- Otherwise, target logs at the boundaries that distinguish hypotheses. Never log everything and grep.
- Tag every debug log with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup becomes a single grep.
- Performance regressions: establish a baseline (timer, profiler, query plan), then bisect. Measure first, fix second.

When a hypothesis fails, revise it using evidence. Never stack a fix on a failed attempt.
After three consecutive probes yield no new evidence, stop repeating them. Change the diagnostic approach or report the blocker.

## Phase 5: Fix, verify, escalate

Hand off to the **tdd** skill: turn the minimised repro into a failing test at the right seam, watch it fail, fix, watch it pass, then re-run the Phase 1 loop against the original un-minimised scenario.

Check the seam first. A seam too shallow to replicate the chain that triggered the bug gives false confidence. When no correct seam exists, that is a finding: flag it for the **improve-codebase-architecture** skill.

Stop after three failed fixes. Fixes that each reveal a new problem in a new place signal a wrong architecture, not a wrong hypothesis. Discuss the architecture with the user before a fourth attempt.

## Phase 6: Cleanup

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop).
- [ ] Regression test passes, or the missing seam is documented.
- [ ] All `[DEBUG-...]` instrumentation removed (`grep` the prefix).
- [ ] Throwaway harnesses deleted, or retained in the platform temporary directory with their location reported.
- [ ] The verified hypothesis is stated in the commit message.
