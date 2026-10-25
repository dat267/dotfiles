---
name: code-review
description: Manually audit a codebase for logic flaws, concurrency bugs, security vulnerabilities, parity gaps against specs, and measured performance problems. Reproduce findings before fixing them, then implement and verify repairs. Invoked explicitly, optionally with a scope or audit-only argument.
disable-model-invocation: true
---

# Code review

The default workflow audits the whole first-party codebase, reproduces each
finding, records it, then repairs and verifies it. Instructions after the
invocation can narrow the scope, set a time budget, request audit-only, or
resume existing findings. Honor those limits. Invocation is not permission to
push, release, or install dependencies.

## 1. Establish the baseline

- Read the workspace's agent instructions, architecture notes, and contributing or
  testing docs (for example `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, or
  `docs/`). When a TDD or debugging skill is available, use it; otherwise follow
  the red-first loop in section 4.
- If the workspace uses version control, record the working-tree status and the
  current commit. Preserve existing edits; never reset, stash, or overwrite
  someone else's work.
- If the project pins specs, confirm the pin from the
  workspace's own documentation, not from memory. Treat the specs as
  read-only. When the pin is missing, dirty, or mismatched, say so and do not
  claim parity was verified.
- Run the workspace's own gate (lint, vet, typecheck, test) as a baseline.
  Record pre-existing failures so a new one can be distinguished from them.
- Track scope, evidence, repairs, and verification in a coverage ledger, as
  working notes or a session plan. Do not create a ledger file in the repository
  unless the workspace already keeps review artifacts there or the user agrees.

## 2. Inventory and inspect systematically

Keep a coverage ledger while working: which areas were inspected, which were
not applicable and why, and which remain. It lives in your working notes, not in
the repository, unless a location is agreed.

Inventory first-party production code, tests, scripts, build and release
workflows, and configuration. Exclude vendored dependencies, generated data,
and build output. Work in bounded slices until coverage is complete or the
budget runs out. Prioritize trust boundaries, persistence, cancellation and
shutdown, churn hotspots, files that past fixes touched, and recent changes, but
do not stop at the first bug or review only recent diffs. Trace values through
callers, callees, and error paths: a search result or analyzer warning marks an
area to inspect, not a finding.

### Review lenses

1. **Parity**, only when the project ports or mirrors specs: read the
   corresponding spec and compare observable behavior, defaults,
   null and empty handling, language-specific semantics (truthiness, string and
   number encoding), error behavior, path and URL rules, serialized bytes and
   key order, and persistence round-trips. Check documented divergences first.
   A difference alone is not a bug. A bug shared with the specs is not a
   parity finding.
2. **Logic:** trace state machines and invariants, boundary conditions,
   ordering, stale snapshots, retry and recovery transitions, partial I/O,
   resource cleanup, cancellation, and error propagation. Include malformed
   external input only where it can reach the production boundary.
3. **Concurrency:** establish the owner of every shared state on a reviewed
   path. Trace locks and lock order, callbacks and reentrancy, admission
   bounds, cancellation, worker handoffs, shutdown draining, and lifetimes.
   Prove a feasible interleaving; a mutex or a thread by itself is not
   suspicious.
4. **Security:** state the attacker, the input, the trust boundary, and the
   affected asset. Trace path traversal and symlinks, command and argument
   injection, credential leakage, token validation, redirects and SSRF,
   untrusted plugin or provider data, file permissions, terminal control
   injection, resource exhaustion, and update or download integrity. Account
   for intentional capabilities and user-granted authority. Use synthetic
   secrets, local servers, and disposable directories; never exploit real
   systems or print real credentials.
5. **Performance:** trace input-scaled loops, repeated scans and copies,
   allocation growth, I/O under locks, unbounded queues, and render or stream
   paths. Require a concrete workload and a measured baseline, an allocation
   test, or a reproducible stall. An apparently expensive operation is not a
   bottleneck. Do not add speculative caches, thresholds, workers, or fast
   paths.
6. **Design:** note where understanding one concept requires bouncing between
   many small modules, where an interface is as complex as its implementation,
   and where pure functions were extracted for testability while the real bugs
   hide in the call sites. Apply the **deletion test**: would deleting this
   module concentrate complexity (it was doing real work) or merely move it
   (shallow)? Name the **seam** where behavior can vary without touching
   callers. Report these as design findings; they are not defects and must not
   be refactored without the user's agreement.

### Avoid missed findings

- List untrusted entry points (arguments, files, network, environment, plugin
  or provider data) and dangerous sinks (process execution, file writes,
  deserialization, credentials, queries). Trace each reachable pair; an
  untraced pair is an unverified area, not a clean one.
- Before inspecting an area, write two or three concrete ways it could be
  wrong, then try to falsify each.
- Apply a failure matrix at each boundary: empty and nil, error path, timeout,
  cancellation, partial write, permission denied, offline and retry, malformed
  and oversized input, concurrent mutation, restart and replay.
- A clean area names the files read and the probes attempted. Record unverified
  separately from passed; do not turn absence of evidence into a pass.
- Read the area's tests for branches without assertions and inspect those
  branches by hand. A test gap is a verification gap, not a defect.

## 3. Reproduce and record before repairing

For each candidate, establish a reachable scenario, the actual result, the
expected result and its authority, the root cause, and the user impact. The
expected result comes from the workspace's contract or the pinned specs, not
from personal preference or another project's convention. Minimize the case and
include a matching control. Reject scenarios that depend only on impossible
internal state, documented divergences, or unsupported features. If a candidate
cannot be reproduced, keep it explicitly unconfirmed and do not patch it.
Report one finding per root cause and merge duplicates: the same defect reached
through several call sites is one finding.

Record confirmed, unresolved findings before editing production code, using the
workspace's existing tracker (for example `TODO.md`, an issue list, or a findings
doc). If none exists, report the findings in the response and ask before
creating a file. Preserve and deduplicate existing entries, and use this
structure:

```markdown
## <ID>: <severity> <concrete failure>
- Category and affected paths or functions:
- Scenario, expected behavior, actual behavior, and impact:
- Evidence: replay command, decisive output, matching control:
- Authority: spec file and function, or a local invariant:
- Root cause:
- Repair plan: regression test, minimal change, affected callers and platforms:
- Verification: focused test and applicable project gates:
```

Prioritize by reachable impact, not warning count. Keep IDs stable while a
finding is open. Audit-only runs stop after the ledger and the plan.

## 4. Execute confirmed repairs

Continue after planning without asking for permission for each ordinary fix.
Ask before a repair that changes a documented divergence, a public contract, a
trust policy, or that needs destructive action. Keep blocked findings recorded
with the unresolved decision.

For each finding, in priority order:

1. Add the smallest regression test at the supported boundary. Run it and
   observe the intended failure before editing production code. A compile error
   or a broken harness is not the required red signal. For a concurrency bug,
   use controlled handshakes instead of sleeps; for performance, keep the
   pre-change measurement and prefer a stable regression check over a
   wall-clock threshold in ordinary tests.
2. Change only what the evidence demands. Preserve documented invariants, byte
   or wire formats, ownership boundaries, and platform behavior. Do not refactor
   unrelated code or weaken a test to make it pass.
3. Run the failing test again and observe it pass, then run adjacent tests and
   the matching controls. Confirm the original reproduction is resolved and no
   intended behavior was lost.
4. Update authoritative docs when behavior or status changed. Remove the finding
   from the tracker only after its repair is verified, keeping its resolution in
   the coverage ledger. Do not erase unrelated or blocked work.
5. Commit each finished piece before starting the next one. "Finished" means one
   independent unit: a finding's regression plus its minimal fix, or one
   coherent docs or skill change. Confirm the pending changes contain only that
   piece (a version-control status and diff, or the equivalent), so the user's
   unrelated edits and other findings stay out. Follow the workspace's commit
   convention (for example `type(scope): summary`) and state the verification
   actually run. Do not commit a red test, a half-applied repair, or work whose
   focused tests have not passed. If a piece cannot be verified, leave it
   uncommitted, say which check failed, and revert or park it rather than
   committing broken work. If the workspace's rules reserve commits for the
   user, leave the piece staged and say so.

## 5. Verify and hand off

- Run focused and affected tests and the workspace gate. Do not silently skip
  failures or claim a check that was not run.
- If version control is used, inspect the diff and new files for scope,
  accidental secrets, unrelated edits, and whitespace errors.
- Report fixed findings, remaining entries, where the ledger is kept, the
  verification performed, and any required next action.
- State coverage limits plainly: static analysis plus passing tests cannot
  certify the absence of bugs, vulnerabilities, or races.
