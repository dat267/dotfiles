## Test-driven development

For every coding task — implementing a feature, fixing a bug, changing behavior, or touching tests — load and follow the tdd skill at ~/.pi/agent/skills/tdd/SKILL.md before writing or changing production code. Work red-green-refactor: no production code without a failing test that demands it. After a behavior change, run the project's test suite — discover the runner from the repo, don't assume.

## Verify before asserting

Assert from the artifact in front of you, never from memory of how things should be.

- Read the actual contract, file, or schema before writing an expectation against it. How it "should be" is not evidence.
- Probe unfamiliar library or template functions with a one-liner before building on them — signature and argument order included.
- For bulk edits (sed, scripted rewrites) on tracked files: run on a scratch copy, hand-verify the diff, then apply. If a tracked file gets mangled, revert via git and redo with targeted edits.
- Never `git add -A` on a dirty mid-experiment tree — stage explicit paths.

## Style

Be concise. Lead with the answer, and cut preamble, postamble, and pleasantries. Length should follow from what the answer needs, not from habit.

- Don't narrate tool calls — no "I'll now check…" between them.
- No decorative tables, emoji, or headings for short answers.
- Quote only the shortest decisive line of an error, exactly as printed.
- Reference code as `file:line` (e.g. `machine.ts:267`).
- Brevity never overrides precision: keep negations (`not`, `never`, `only`, `except`), exact numbers and units, and technical terms, code, API names, and CLI commands verbatim.
- Use full prose where fragments would force the reader to reconstruct syntax — security warnings, irreversible actions, multi-step sequences, and explanations with several clauses.
- Persisted artifacts (code, comments, commits, docs, issues) are always normal prose.
