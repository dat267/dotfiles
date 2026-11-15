---
name: code-maintenance
description: Audit a codebase or one area of it for logic, concurrency, security, spec-parity, and measured performance bugs, dead code, and code that could be simpler; confirm each finding, then repair and verify it. Use when asked to audit, harden, clean up, simplify, or do a maintenance pass, or when debugging finds a missing test seam or a design defect. Not for reviewing a single diff or fixing one known bug.
---

# Code maintenance

Audit the code, confirm each finding, repair and verify it, and record what you leave open.

**Scope.** When the user invokes this skill, the scope is the whole first-party codebase. When you pick it yourself or another skill hands you a finding, the scope is that finding's area: say so, and offer the wider audit instead of starting it. Honor instructions that narrow the scope, set a budget, ask for audit-only, or resume existing findings. Invocation is not permission to push, release, or install dependencies.

## 1. Baseline

- Read the workspace's agent, architecture, contributing, and testing docs (for example `AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `docs/`) and its `TODO.md`. Documented structure and planned work are not findings.
- For bug findings, use a TDD or debugging skill when one is available; otherwise follow section 4. Dead code and simplicity repairs always follow section 4's covering-test path.
- Record the working-tree status and the current commit. Never reset, stash, or overwrite someone else's edits.
- If the project pins specs, confirm the pin from its own docs and treat the specs as read-only. If the pin is missing, dirty, or mismatched, say so and claim no parity.
- Run the workspace gate (lint, typecheck, tests) and record pre-existing failures.

## 2. Inventory and inspect

List every in-scope file with a command such as `git ls-files`, and count them: first-party code, tests, scripts, build and release workflows, and configuration, excluding vendored, generated, and build output.

Keep a coverage ledger in a scratch file outside the repository: one row per file with its status (pending, inspected, unverified, or not applicable and why), the lenses applied, and the probes tried. Mark a file unverified when you read it but could not settle a probe. Keep the full finding records there too. Update it as you go, and reread it after any break or context summary.

Cover the codebase; do not sample it:

- Split the files into slices by component, each small enough to read in full, ordered by risk: trust boundaries, persistence, cancellation and shutdown, churn hotspots, files past fixes touched, and recent changes first. A larger codebase means more slices, not lighter reading.
- A file is inspected only when you have read all of it and applied every lens that fits. A search hit, listing, outline, analyzer warning, or partial read is not inspection. Trace values through callers, callees, and error paths.
- Stop only when every row is inspected, unverified, or not applicable, or the budget runs out. Finding a few bugs or a clean-looking area is not a reason to stop.
- When the budget runs out, say so and leave the remaining rows pending. If a later run finds the ledger gone, it redoes the inventory, treats every file as pending, and skips findings already in the tracker.

### Lenses

1. **Parity** (only when the project ports or mirrors specs): compare observable behavior with the matching spec: defaults, null and empty handling, language semantics such as truthiness and encoding, errors, path and URL rules, serialized bytes and key order, and persistence round-trips. Check documented divergences first. A difference alone is not a bug, and a bug the specs share is not a parity finding.
2. **Logic:** state machines and invariants, boundaries, ordering, stale snapshots, retry and recovery, partial I/O, cleanup, cancellation, and error propagation. Consider malformed input only where it can reach a production boundary.
3. **Concurrency:** name the owner of each piece of shared state, and trace locks and lock order, reentrancy, admission bounds, handoffs, shutdown draining, and lifetimes. Prove a bad interleaving is feasible; a mutex or a thread is not suspicious by itself.
4. **Security:** name the attacker, input, trust boundary, and asset. Trace path traversal and symlinks, command injection, credential leaks, token validation, redirects and SSRF, untrusted plugin or provider data, file permissions, terminal control injection, resource exhaustion, and download integrity. Account for capabilities the user granted on purpose. Use synthetic secrets, local servers, and disposable directories; never exploit real systems or print real credentials.
5. **Performance:** loops that scale with input, repeated scans and copies, allocation growth, I/O under locks, unbounded queues, and render or stream paths. Require a measured baseline, an allocation test, or a reproducible stall; looking expensive is not a bottleneck. Add no speculative caches, workers, or fast paths.
6. **Design:** one concept spread across many small modules, interfaces as complex as their implementations, and pure functions extracted for tests while the bugs live in the call sites. Apply the deletion test: does deleting the module concentrate complexity (it did real work) or just move it (it was shallow)? Name the seam where behavior can vary without touching callers. Design findings are not defects; do not refactor them without the user's agreement.
7. **Dead code:** unreachable branches; unused functions, parameters, imports, options, and files; flags or fallbacks no supported configuration takes. Before calling code dead, rule out dynamic dispatch, reflection, string lookups, entry points in build, package, or CI files, config registrations, plugin and hook interfaces, platform and version guards, and callers outside the repository. Code only its own tests use is dead, and those tests go with it. Exported or documented API is a public contract even with no caller in the repository.
8. **Simplicity:** code longer or more indirect than it needs to be: duplicated logic, a hand-rolled copy of a library function or an existing helper, layers, options, or generality nothing uses, checks for impossible states, and tangled control flow. Name the simpler version and why it behaves the same. Stay inside one module and its interface; moving boundaries is a design finding. The rewrite must be shorter, remove a concept, or remove a way to get it wrong; taste is not a finding.

### Avoid missed findings

- List untrusted entry points (arguments, files, network, environment, plugin data) and dangerous sinks (process execution, file writes, deserialization, credentials, queries), and trace each reachable pair. An untraced pair is unverified.
- Before inspecting an area, write down two or three ways it could be wrong, and try to falsify each.
- At each boundary, check empty and nil, error paths, timeout, cancellation, partial writes, permission denied, offline and retry, malformed and oversized input, concurrent mutation, and restart and replay.
- Read the tests for branches without assertions, and inspect those branches by hand. A test gap is a verification gap, not a defect.

## 3. Confirm and record

For each bug candidate, establish a reachable scenario, the actual and expected results, the authority for the expected result (the workspace's contract or pinned specs, not preference), the root cause, and the user impact. Minimize the case and add a matching control. Reject scenarios that need impossible internal state, documented divergences, or unsupported features. A candidate you cannot reproduce stays unconfirmed and gets no patch. One root cause is one finding, however many call sites reach it.

Dead code and simplicity findings need no failing case. Dead code is confirmed by each reach path you ruled out and the search that ruled it out; with any path left open, it stays unconfirmed and is not deleted. A simplification is confirmed by the simpler version and the tests that pin the behavior both versions share. Rate them low unless they hide a bug, which makes it a logic finding.

Before editing production code, record each confirmed finding you will not repair in this run. Record a repair when it gets blocked or fails verification.

- Add one line per bug finding to the workspace's unfinished-work list, such as a `TODO.md` section, under the priority its impact warrants: the ID, severity, affected path, and concrete failure, readable without the full record. Group dead code and simplicity findings into one line per area. If the workspace has no such list, report the findings and ask before creating a file.
- Preserve existing entries and do not duplicate them. Do not create a separate findings file; it duplicates the tracker and drifts.
- Keep the full record in the ledger, in this form:

```markdown
<ID>: <severity> <concrete failure>
- Category and affected paths or functions:
- Scenario, expected and actual behavior, and impact:
- Evidence: replay command, decisive output, matching control:
- Authority: spec file and function, or a local invariant:
- Root cause:
- Repair plan: regression test, minimal change, affected callers and platforms:
- Verification: focused test and applicable gates:
```

For dead code or simplicity, the scenario names the code and its cost to the reader, the evidence lists the reach paths ruled out or the simpler version, and the repair plan names the covering tests.

Prioritize by reachable impact, not warning count, and keep IDs stable while a finding is open. An audit-only run stops here.

## 4. Repair

Repair without asking for each ordinary fix. Ask first when a repair would change a documented divergence, a public contract, or a trust policy, or needs a destructive action, and record blocked findings with the open decision. Deleting tracked dead code is not destructive, since history restores it.

For each finding, in priority order:

1. For a bug, add the smallest regression test at the supported boundary and see it fail for the intended reason before touching production code; a compile error or broken harness does not count. For concurrency, use controlled handshakes, not sleeps. For performance, keep the pre-change measurement, and prefer a stable check over a wall-clock threshold. For dead code or simplicity, first make sure tests cover the behavior the change must keep, adding a test that passes on the current code when they do not.
2. Change only what the evidence demands. Preserve documented invariants, byte and wire formats, ownership boundaries, and platform behavior. Touch nothing outside the finding, and never weaken a test to make it pass. A simplification leaves its covering tests unchanged.
3. Run the regression test and see it pass, or the covering tests and see them still pass, then the adjacent tests. For a bug, also run the matching controls and confirm the original reproduction is resolved. Confirm no intended behavior was lost.
4. Update the docs that own the changed fact: `TODO.md` for remaining work, `ARCHITECTURE.md` for structure, `AGENTS.md` for conventions, `README.md` for usage. Remove a tracker line only after its repair is verified. Do not erase unrelated or blocked work.
5. Commit each finished piece before starting the next: a regression test plus its fix, a deletion or simplification plus any covering test, or one coherent docs change. Check status and diff so the commit holds only that piece, follow the workspace's commit convention, and state the verification you ran. Never commit a red test, a half-applied repair, or unverified work: leave it uncommitted, say which check failed, and revert or park it. If the workspace reserves commits for the user, stage the piece and say so.

## 5. Hand off

- Run the focused and affected tests and the workspace gate. Never hide a failure or claim a check you did not run.
- Inspect the diff and new files for scope, secrets, unrelated edits, and whitespace errors.
- Report each fixed finding in one line, the full record of each open finding (the ledger may not outlive the run), the verification you ran, and any action the user must take.
- Report coverage: files inspected out of the total, unverified files and their open probes, what remains, and the ledger's path. Do not call the audit complete while any row is pending.
- Say plainly that static analysis and passing tests cannot prove the absence of bugs, vulnerabilities, or races.
