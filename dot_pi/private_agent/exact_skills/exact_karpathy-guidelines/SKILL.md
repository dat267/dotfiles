---
name: karpathy-guidelines
description: Behavioral guardrails that reduce common LLM coding mistakes. State assumptions, write the minimum code, keep edits surgical, and verify before claiming done. Use when writing, editing, reviewing, or refactoring code, or when a task is ambiguous or multi-step. Derived from Andrej Karpathy's observations on LLM coding pitfalls.
license: MIT
---

# Karpathy Guidelines

Guardrails based on [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876)
about how LLMs go wrong when coding. They trade speed for caution, so skip
them for trivial work. The workspace's own instructions (`AGENTS.md`,
`CLAUDE.md`, `CONTRIBUTING.md`, editor rule directories) and its existing
conventions override this skill.

## 1. Think before coding

Proceed on assumptions that are low-risk and reversible. Ask when the
ambiguity affects scope, correctness, security, or anything irreversible.

- Ask when competing readings of the task lead to materially different changes.
- When a simpler approach exists, say so. Push back with evidence.
- Never present an unverified assumption as fact.

## 2. Write the minimum code

Implement exactly what the task asks, and nothing speculative.

- No features beyond the request.
- No abstraction for code used once.
- No flexibility or configuration nobody asked for.
- No handling for errors that cannot occur.
- If your change takes 200 lines and could take 50, rewrite it before handing
  it over.

Ask: "Would a senior engineer call this overcomplicated?" If so, simplify.

## 3. Keep changes surgical

Touch only what the task requires, and clean up only your own mess.

- Leave adjacent code, comments, and formatting alone.
- Do not refactor code that already works.
- Match the surrounding style, even where you would choose differently.
- Report unrelated dead code instead of deleting it.
- Remove the imports, variables, and functions your change left orphaned.

Gate: every changed line traces back to the request.

```bash
git diff --stat   # scope of the change
git diff          # each hunk traces to the request
```

Without version control, read back every file you touched in full and hold each
hunk to the same test.

## 4. Verify before claiming done

Turn the task into a verifiable goal and define the check before writing code.
Weak goals such as "make it work" force constant clarification. For multi-step
work, plan one verification command per step, and share the plan only when
coordination or approval needs it.

The failing-test loop belongs to the **tdd** skill, and root-causing to
**systematic-debugging**, when they are available. Without them: a fix starts
with a test that reproduces the bug, new behavior starts with a failing test,
and a refactor passes the same tests before and after.

Gate: run the relevant tests.

When revising a prompt or skill, use [prompt-evaluation.md](prompt-evaluation.md)
to evaluate instruction compliance.
