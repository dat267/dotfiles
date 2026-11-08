---
name: systematic-debugging
description: Root-cause debugging discipline for bugs that resist the first look. Build a red-capable feedback loop, trace the bad value to its source, and fix there. Use when something is broken, throwing, failing, flaky, slow, or sitting in a multi-layer system, and the cause is not already obvious.
---

# Systematic Debugging

Find the root cause before attempting any fix. A fix that only silences the
symptom is a failure.

Skip this skill when the fix is obvious: a typo, a config line, a commit to
revert. It is for bugs that resist the first look.

## Redact

- Redact every secret as `<REDACTED>` in commands, output, and captured
  artifacts. Keep credentials in environment variables.
- Use a writable platform temp directory (`$TMPDIR`, or the platform's temp
  API). Never assume `/tmp` exists.
- When redacted output is not enough to diagnose the bug, say so and ask.

## Phase 1: Build a feedback loop

Build a tight pass/fail signal for the user's bug, and use it to judge every
bisection step, hypothesis, and piece of instrumentation. Aim for reproduction
without repeating probes that taught you nothing. Put explicit timeouts and
iteration limits on network calls, suspected hangs, and loops.

Build one, roughly in this order of preference:

1. A failing test at any seam that reaches the bug: unit, integration, e2e.
2. A CLI invocation on a fixture input, with stdout diffed against a snapshot.
3. A curl or HTTP script against a running server.
4. A captured trace (request, payload, event log) replayed through the code
   path.
5. A throwaway harness in the platform temp directory that drives the bug path
   in one call.
6. A property or fuzz loop: 1000 random inputs for "sometimes wrong".
7. A bisection harness driven by `git bisect run`, or the equivalent in the
   project's version control.
8. A differential loop: the same input through old and new, outputs diffed.
9. A user-relay loop for machines you cannot reach: hand the user one exact
   command and take back the redacted output.

Then tighten it: faster (cache the setup), sharper (assert the exact symptom),
more deterministic (pin the time, seed the RNG, freeze the network). A
2-second deterministic loop beats a 30-second flaky one.

For flaky bugs, raise the reproduction rate with bounded repetition, stress,
and narrower timing windows. Record the observed failure rate. You do not need
a fixed rate to proceed, but report how it limits your confidence.

**Gate.** Phase 1 ends when you can point to one command you have already run,
with its invocation and redacted output shown, that is:

- [ ] Red-capable: it drives the bug path and asserts the user's exact symptom.
- [ ] Deterministic: same verdict every run (for a flaky bug, a pinned high
      rate).
- [ ] Fast: seconds, not minutes.
- [ ] Runnable unattended, or through a user-relay loop with a predictable
      turnaround.

Read the relevant code, configuration, and logs while you build the loop, and
label early hypotheses as unverified. Apply no speculative fix before you have
a reproduction or a decisive diagnostic check. If no loop is possible, report
what you tried and ask for environment access, a redacted artifact, or
permission to add instrumentation.

## Phase 2: Reproduce and minimize

Run the loop and watch it go red.

- [ ] The failure is the user's symptom, not a nearby different one.
- [ ] It reproduces across runs, or at the pinned high rate.
- [ ] The exact symptom is captured: error text, wrong output, or timing.

Minimize: cut inputs, callers, config, data, and steps one at a time,
re-running after each cut, and keep only what is load-bearing. You are done
when removing any remaining element turns the loop green. The minimal repro
becomes the regression test.

## Phase 3: Trace to the source

Follow the evidence toward the origin, and keep every hypothesis unverified
until a diagnostic check supports it.

Find working examples of the same behavior and list every difference, however
small. Read reference implementations completely; never skim. Check
dependencies, config, and assumptions.

Trace the bad value backward: where did it come from, and what passed it in?
Keep going up until you reach the source, and fix it there, never at the
symptom.

In multi-layer systems (CI to build to signing, API to service to database),
instrument every component boundary before proposing a fix. Log what enters
and leaves each layer, and check that environment and config propagate. Run
once to see which layer breaks, then investigate that layer.

Recent changes are prime suspects: check the version-control history and diff,
new dependencies, and config or environment drift. Without history, compare
against a known-good copy or the last released artifact.

## Phase 4: Hypothesize and test

Form only falsifiable hypotheses that the evidence supports. When several
explanations fit, rank them, but never invent candidates to fill a quota.

Give each hypothesis a testable prediction, and sharpen or drop any that lacks
one. Share hypotheses only when the user's input or approval affects the next
probe; otherwise test them without narrating.

Change one variable at a time, each probe testing one prediction.

- Prefer direct inspection (a REPL, `python -m pdb`, `node --inspect`) over
  logging. One breakpoint beats ten log lines.
- Otherwise, log only at the boundaries that tell hypotheses apart. Never log
  everything and grep.
- Tag every debug log with a unique prefix such as `[DEBUG-a4f2]`, so cleanup
  is a single grep.
- For performance regressions, establish a baseline (a timer, a profiler, a
  query plan), then bisect. Measure first, fix second.

When a hypothesis fails, revise it from the evidence. Never stack a fix on a
failed attempt. After three probes in a row yield no new evidence, stop
repeating them: change the diagnostic approach or report the blocker.

## Phase 5: Fix, verify, escalate

Fix red-first. Turn the minimized repro into a failing test at the right seam,
watch it fail, fix the code, watch it pass, then re-run the Phase 1 loop
against the original, unminimized scenario. When a **tdd** skill is available,
follow it. When the stack has no test harness, use a substitute check: a
reproducible command or fixture that fails before the fix and passes after.

Check the seam first. A seam too shallow to replay the chain that triggered the
bug gives false confidence. When no correct seam exists, that is a finding in
itself: hand it, with the repro, to a **code-maintenance** skill when one is
available, scoped to that area, and otherwise report it directly.

Stop after three failed fixes. When each fix uncovers a new problem somewhere
else, the architecture is wrong, not the hypothesis. Discuss the architecture
with the user before a fourth attempt.

## Phase 6: Clean up

- [ ] The original repro no longer reproduces (re-run the Phase 1 loop).
- [ ] The regression test passes, or the missing seam is documented.
- [ ] All `[DEBUG-...]` instrumentation is removed (grep for the prefix).
- [ ] Throwaway harnesses are deleted, or kept in the platform temp directory
      with their location reported.
- [ ] The verified hypothesis is stated in the commit message, or in the
      change description when there is no commit.
