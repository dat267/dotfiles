---
name: diagnosing-bugs
description: Diagnosis loop for hard bugs and performance regressions — build a red/green feedback loop before theorizing. Use when the user reports something broken, throwing, failing, flaky, or slow and the cause is not already obvious.
---

# Diagnosing Bugs

A discipline for hard bugs. Skip phases only when explicitly justified.

Exit early if the fix is already obvious (a typo, a config line, a reverted commit) — just fix it. This skill is for bugs that resist the first look.

## Redact

This skill has you show commands, outputs, and captured artifacts. **Redact every secret first**: write `<REDACTED>` in its place. Build loops against env vars, so credentials stay in the environment rather than in what you show. Captured artifacts carry auth headers: quote only the lines that carry the signal. Scratch files go in `/tmp`.

If redacted output is not enough to diagnose the bug, say so and ask.

## Phase 1: Build a feedback loop

**This is the skill.** Everything else is mechanical. If you have a **tight** pass/fail signal for the bug (one that goes red on _this_ bug), you will find the cause; bisection, hypothesis-testing, and instrumentation all just consume it. If you don't have one, no amount of staring will save you.

Spend disproportionate effort here. Be aggressive. Be creative. Refuse to give up.

### Ways to construct one, in roughly this order

1. **Failing test** at whatever seam reaches the bug: unit, integration, e2e.
2. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
3. **Curl / HTTP script** against a running server.
4. **Replay a captured trace.** Save a real request / payload / event log to disk; replay it through the code path in isolation.
5. **Throwaway harness.** Minimal subset of the system (one function, mocked deps) that exercises the bug path in a single call. Build it in `/tmp`.
6. **Property / fuzz loop.** If the bug is "sometimes wrong output", run 1000 random inputs and look for the failure mode.
7. **Bisection harness.** If the bug appeared between two known states (commit, dataset, version), automate "boot at state X, check, repeat" so you can `git bisect run` it.
8. **Differential loop.** Same input through old vs new (or two configs), diff the outputs.
9. **User-relay loop.** For system-level bugs on machines you cannot touch (ssh/sshd, sandboxed paths, another host): hand the user **one exact command** to run there and have them paste the redacted output back. Still a loop — the human is a relay, not a co-reasoner. Give the next command the moment the output lands.

Build the right loop and the bug is 90% fixed.

### Tighten the loop

Once you have _a_ loop, tighten it: faster (cache setup, skip unrelated init), sharper (assert the specific symptom, not "didn't crash"), more deterministic (pin time, seed RNG, freeze network). A 30-second flaky loop is barely better than none; a 2-second deterministic one is a debugging superpower.

### Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**. Loop the trigger 100×, add stress, narrow timing windows. A 50%-flake is debuggable; 1% is not.

### When you genuinely cannot build a loop

Stop and say so. List what you tried. Ask the user for: (a) access to the reproducing environment, (b) a redacted captured artifact (log dump, HAR, screenshot with timestamps), or (c) permission to add temporary instrumentation. Do **not** proceed to hypothesise without a loop.

### Completion criterion: a tight loop that goes red

Phase 1 is done when you can name **one command** that you have **already run at least once** (show the invocation and its redacted output), and that is:

- [ ] **Red-capable**: drives the actual bug path and asserts the **user's exact symptom** — can go red on this bug, green once fixed. Not "runs without erroring".
- [ ] **Deterministic**: same verdict every run (flaky bugs: a pinned high reproduction rate).
- [ ] **Fast**: seconds, not minutes.
- [ ] **Runnable unattended** by you, or via the user-relay loop with predictable turnaround.

If you catch yourself reading code to build a theory before this command exists, **stop: that is the exact failure this skill prevents.** No red-capable command, no Phase 2.

## Phase 2: Reproduce + minimise

Run the loop. Watch it go red.

- [ ] The failure is the **user's** described symptom, not a nearby different failure. Wrong bug = wrong fix.
- [ ] Reproducible across runs (or at the pinned high rate).
- [ ] Exact symptom captured (error text, wrong output, timing) so later phases can verify the fix.

Then **minimise**: cut inputs, callers, config, data, steps one at a time, re-running after each cut, keeping only what is load-bearing. A minimal repro shrinks the hypothesis space and becomes the regression test. Done when removing any remaining element turns the loop green.

## Phase 3: Hypothesise

Generate **3–5 ranked hypotheses** before testing any. Single-hypothesis generation anchors on the first plausible idea.

Each must be **falsifiable** — state the prediction: "If <X> is the cause, then <changing Y> makes it disappear / <changing Z> makes it worse." If you cannot state the prediction, it is a vibe: discard or sharpen it.

**Show the ranked list to the user before testing.** They often hold domain knowledge that re-ranks instantly ("we just changed that config"), or have already ruled some out. Cheap checkpoint. Don't block on it; proceed with your ranking if they're away.

## Phase 4: Instrument

Each probe maps to one prediction from Phase 3. **Change one variable at a time.**

- Prefer direct inspection (REPL, `python -m pdb`, `node --inspect`) over logging. One breakpoint beats ten logs.
- Otherwise, targeted logs at the boundaries that distinguish hypotheses. Never "log everything and grep".
- **Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]` — cleanup becomes a single grep. Untagged logs survive; tagged logs die.
- **Perf branch**: for performance regressions, logs are usually wrong. Establish a baseline measurement (timer, profiler, query plan), then bisect. Measure first, fix second.

## Phase 5: Fix + regression test

Hand off to the **tdd skill**: turn the minimised repro into a failing test at the right seam, watch it fail, fix, watch it pass, then re-run the Phase 1 loop against the original un-minimised scenario.

One extra judgment call before handing off: is there a **correct seam** — one where the test exercises the real bug pattern as it occurs at the call site? If the only available seam is too shallow to replicate the chain that triggered the bug, a regression test there gives false confidence.

**If no correct seam exists, that itself is a finding.** Note it and flag it for the `improve-codebase-architecture` skill — the codebase structure is preventing the bug from being locked down.

## Phase 6: Cleanup

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop)
- [ ] Regression test passes (or the missing seam is documented)
- [ ] All `[DEBUG-...]` instrumentation removed (`grep` the prefix)
- [ ] Throwaway harnesses deleted (or left in `/tmp`, which is understood to be ephemeral)
- [ ] The verified hypothesis is stated in the commit message, so the next debugger learns
