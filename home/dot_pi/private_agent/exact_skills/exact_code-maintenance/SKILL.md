---
name: code-maintenance
description: Audit a codebase or one area of it for logic flaws, concurrency bugs, security vulnerabilities, parity gaps against specs, measured performance problems, dead code, and code that could be simpler, confirm each finding, then repair and verify it. Use when asked to audit, harden, clean up, simplify, or do a maintenance pass, or when debugging finds a missing test seam or a design defect. Not for reviewing a single diff or fixing one known bug.
---

# Code maintenance

The workflow audits code, confirms each finding, records it, then repairs and verifies it.

**Scope.** When the user invokes this skill, the default scope is the whole first-party codebase. When you pick it yourself, or another skill hands you a finding, the scope is that finding and the area it lives in: say so, and offer the wider audit instead of starting it. Either way, honor any instructions that narrow the scope, set a time budget, ask for audit-only, or resume existing findings. Invocation is not permission to push, release, or install dependencies.

## 1. Establish the baseline

- Read the workspace's agent instructions, architecture notes, and contributing or testing docs (for example `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, or `docs/`). Use a TDD or debugging skill when one is available; otherwise follow the red-first loop in section 4.
- Read `ARCHITECTURE.md` for the component map and `TODO.md` for planned or known work, when they exist. Account for documented structure and planned work instead of reporting them as findings.
- Under version control, record the working-tree status and the current commit. Preserve existing edits: never reset, stash, or overwrite someone else's work.
- If the project pins specs, confirm the pin from the workspace's own documentation, not from memory, and treat the specs as read-only. When the pin is missing, dirty, or mismatched, say so and do not claim parity was verified.
- Run the workspace's own gate (lint, vet, typecheck, test) as a baseline, and record pre-existing failures so you can tell new ones apart.

## 2. Inventory and inspect systematically

Inventory first-party production code, tests, scripts, build and release workflows, and configuration. Exclude vendored dependencies, generated data, and build output. List every file in scope with a command (for example `git ls-files`), not from memory or a directory skim, and count them.

Keep a coverage ledger in a scratch file outside the repository, so it survives a long session: one row per file with its status (pending, inspected, or not applicable and why) and the lenses applied. Update it as you go, and reread it after any break or context summary.

Cover the codebase, do not sample it:

- Split the inventory into slices by component, each small enough to read in full, and work through every slice. A large codebase means more slices, not a lighter read of each.
- A file counts as inspected only when you have read all of it and applied every lens that fits. A search hit, a file listing, an outline, or reading the first part of a file is not inspection.
- Finishing a slice, finding a few bugs, or reaching a clean-looking area is not a reason to stop. Stop only when every row is inspected or not applicable, or the user's budget runs out.
- When the budget runs out, say so, and leave the remaining rows pending in the ledger so the next run resumes there.

Start with trust boundaries, persistence, cancellation and shutdown, churn hotspots, files that past fixes touched, and recent changes, but do not stop at the first bug or review only recent diffs. Trace values through callers, callees, and error paths. A search hit or an analyzer warning marks an area to inspect; it is not a finding.

### Maintenance lenses

1. **Parity** (only when the project ports or mirrors specs): read the matching spec and compare observable behavior, defaults, null and empty handling, language-specific semantics (truthiness, string and number encoding), error behavior, path and URL rules, serialized bytes and key order, and persistence round-trips. Check documented divergences first. A difference alone is not a bug, and a bug the specs share is not a parity finding.
2. **Logic:** trace state machines and invariants, boundary conditions, ordering, stale snapshots, retry and recovery transitions, partial I/O, resource cleanup, cancellation, and error propagation. Consider malformed external input only where it can reach the production boundary.
3. **Concurrency:** establish who owns every piece of shared state on a reviewed path. Trace locks and lock order, callbacks and reentrancy, admission bounds, cancellation, worker handoffs, shutdown draining, and lifetimes. Prove that a bad interleaving is feasible; a mutex or a thread is not suspicious by itself.
4. **Security:** name the attacker, the input, the trust boundary, and the asset at risk. Trace path traversal and symlinks, command and argument injection, credential leakage, token validation, redirects and SSRF, untrusted plugin or provider data, file permissions, terminal control injection, resource exhaustion, and update or download integrity. Account for intentional capabilities and authority the user granted. Use synthetic secrets, local servers, and disposable directories; never exploit real systems or print real credentials.
5. **Performance:** trace loops that scale with input, repeated scans and copies, allocation growth, I/O under locks, unbounded queues, and render or stream paths. Require a concrete workload with a measured baseline, an allocation test, or a reproducible stall. An operation that looks expensive is not therefore a bottleneck. Add no speculative caches, thresholds, workers, or fast paths.
6. **Design:** note where understanding one concept means bouncing between many small modules, where an interface is as complex as its implementation, and where pure functions were extracted for testability while the real bugs hide in the call sites. Apply the **deletion test**: would deleting this module concentrate complexity (it was doing real work) or merely move it (it was shallow)? Name the **seam** where behavior can vary without touching callers. Report these as design findings. They are not defects, and must not be refactored without the user's agreement.
7. **Dead code:** find unreachable branches, unused functions, parameters, imports, options, and files, and flags or fallbacks that no supported configuration takes. Before calling code dead, rule out every way to reach it: dynamic dispatch, reflection, string lookups, entry points declared in build, package, or CI files, registrations in config, plugin and hook interfaces, platform and version guards, and callers outside the repository. Code that only its own tests use is dead, and its tests go with it. Exported or documented API is a public contract even with no caller in the repository.
8. **Simplicity:** find code that does its job in a longer or more indirect way than it needs: duplicated logic, a hand-rolled copy of a standard library function or an existing helper, layers, options, or generality nothing uses, checks for states the code cannot reach, and control flow a reader must untangle. A finding names the simpler version and why it behaves the same. Keep it inside one module and its existing interface; a change that moves boundaries is a design finding. Taste is not a finding: the rewrite must be shorter, remove a concept, or remove a way to get it wrong.

### Avoid missed findings

- List the untrusted entry points (arguments, files, network, environment, plugin or provider data) and the dangerous sinks (process execution, file writes, deserialization, credentials, queries). Trace each reachable pair. An untraced pair is unverified, not clean.
- Before inspecting an area, write down two or three concrete ways it could be wrong, then try to falsify each.
- At each boundary, run through a failure matrix: empty and nil, error path, timeout, cancellation, partial write, permission denied, offline and retry, malformed and oversized input, concurrent mutation, restart and replay.
- A clean area names the files read and the probes tried. Record unverified areas separately from passed ones; absence of evidence is not a pass.
- Read the area's tests for branches without assertions, and inspect those branches by hand. A test gap is a verification gap, not a defect.

## 3. Reproduce and record before repairing

For each candidate, establish a reachable scenario, the actual result, the expected result and the authority for it, the root cause, and the impact on users. The expected result comes from the workspace's contract or the pinned specs, not from personal preference or another project's convention.

Dead code and simplicity findings are confirmed without a failing case. For dead code, the evidence is each reach path you ruled out and the search that ruled it out. For a simplification, the evidence is the simpler version and the tests that pin the behavior both versions share. Rate them low unless the dead or tangled code hides a bug, which makes it a logic finding.

Minimize the case and include a matching control. Reject scenarios that rely on impossible internal state, documented divergences, or unsupported features. A candidate you cannot reproduce stays explicitly unconfirmed and gets no patch. Report one finding per root cause: the same defect reached through several call sites is one finding.

Record each confirmed, unresolved finding before editing production code. The tracker owns the work item; the analysis lives elsewhere:

- Add one line per finding to the workspace's unfinished-work list: the ID, the severity, and the concrete failure, under the priority its impact warrants (for example a `TODO.md` section). If the workspace has no such list, report the finding in your response and ask before creating a file.
- Keep the full record with the run, in your working notes or the response, and cite it by ID from the tracker line. Do not create a findings file next to the tracker; it duplicates the work items and drifts.
- Preserve existing entries and do not duplicate them.
- Dead code and simplicity findings you repair in this run need no tracker line. Record only the ones you leave open.

Use this structure for the full record:

```markdown
<ID>: <severity> <concrete failure>
- Category and affected paths or functions:
- Scenario, expected behavior, actual behavior, and impact:
- Evidence: replay command, decisive output, matching control:
- Authority: spec file and function, or a local invariant:
- Root cause:
- Repair plan: regression test, minimal change, affected callers and platforms:
- Verification: focused test and applicable project gates:
```

Prioritize by reachable impact, not by warning count, and keep IDs stable while a finding is open. An audit-only run stops after the findings and the plan.

## 4. Execute confirmed repairs

Once the plan exists, keep going without asking permission for each ordinary fix. Ask first when a repair would change a documented divergence, a public contract, or a trust policy, or needs a destructive action, and keep blocked findings recorded with the open decision.

For each finding, in priority order:

1. Add the smallest regression test at the supported boundary, run it, and see the intended failure before touching production code. A compile error or a broken harness is not the red signal you need. For a concurrency bug, use controlled handshakes instead of sleeps. For performance, keep the pre-change measurement, and prefer a stable regression check over a wall-clock threshold in ordinary tests. Dead code and simplicity repairs have no red step: first make sure tests cover the behavior the change must keep, and when they do not, add a test that passes on the current code.
2. Change only what the evidence demands. Preserve documented invariants, byte and wire formats, ownership boundaries, and platform behavior. Do not touch code outside the finding, and never weaken a test to make it pass. A simplification must leave the covering tests unchanged and passing.
3. Run the failing test again and see it pass, then run the adjacent tests and the matching controls. Confirm that the original reproduction is resolved and no intended behavior was lost.
4. Update the docs that own the changed fact: `TODO.md` for the remaining work, `ARCHITECTURE.md` for durable structural changes, `AGENTS.md` for instructions or conventions, `README.md` for visible usage. Remove the finding from the tracker only after its repair is verified, and say what was confirmed. Do not erase unrelated or blocked work.
5. Commit each finished piece before starting the next. A finished piece is one independent unit: a finding's regression test plus its minimal fix, or one coherent docs or skill change. Check the pending changes (status and diff, or the equivalent) so they contain only that piece, keeping the user's unrelated edits and other findings out. Follow the workspace's commit convention (for example `type(scope): summary`) and state the verification you actually ran. Never commit a red test, a half-applied repair, or work whose focused tests have not passed. If a piece cannot be verified, leave it uncommitted, say which check failed, and revert or park it. If the workspace's rules reserve commits for the user, leave the piece staged and say so.

## 5. Verify and hand off

- Run the focused and affected tests and the workspace gate. Never skip a failure silently or claim a check you did not run.
- Under version control, inspect the diff and new files for scope, accidental secrets, unrelated edits, and whitespace errors.
- Report the fixed findings, the remaining entries, the verification you ran, and any next action the user must take.
- Report coverage from the ledger: files inspected out of the total in scope, and which files or slices remain. Do not call the audit complete while any row is pending.
- State the limits plainly: static analysis plus passing tests cannot prove the absence of bugs, vulnerabilities, or races.
