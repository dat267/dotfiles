---
name: karpathy-guidelines
description: Behavioral guardrails that reduce common LLM coding mistakes. State assumptions, write the minimum code, keep edits surgical, and verify before claiming done. Use when writing, editing, reviewing, or refactoring code, or when a task is ambiguous or multi-step. Derived from Andrej Karpathy's observations on LLM coding pitfalls.
license: MIT
---

# Karpathy Guidelines

Guardrails derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls. They trade speed for caution. Skip them for trivial work. The workspace's own instructions (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, editor rule directories) and existing conventions override this skill.

## 1. Think before coding

Proceed on low-risk, reversible assumptions. Ask when ambiguity changes scope, correctness, security, or irreversible effects.

- Ask when competing interpretations require materially different changes.
- Name a simpler approach when one exists. Push back with evidence.
- Do not present an unverified assumption as fact.

## 2. Write the minimum code

Implement exactly what the task asks. Add nothing speculative.

- Write no feature beyond the request.
- Extract no abstraction for single-use code.
- Add no flexibility or configuration nobody requested.
- Handle no error that cannot occur.
- If your change takes 200 lines and could take 50, rewrite it before handing it over.

Ask: "Would a senior engineer call this overcomplicated?" If yes, simplify.

## 3. Keep changes surgical

Touch only what the task requires. Clean up only your own mess.

- Never improve adjacent code, comments, or formatting.
- Never refactor code that already works.
- Match the surrounding style, even when you disagree with it.
- Report unrelated dead code. Do not delete it.
- Remove imports, variables, and functions your change orphaned.

Gate: every changed line traces to the user's request.

```bash
git diff --stat   # scope of the change
git diff          # each hunk traces to the request
```

Without version control, read back every file you touched in full and apply the
same test to each hunk.

## 4. Verify before claiming done

Turn the task into a verifiable goal and define the check before writing code.
Weak goals such as "make it work" force constant clarification. For multi-step
work, plan one verification command per step; share the plan only when
coordination or approval is needed.

The failing-test loop belongs to the **tdd** skill and root-causing to
**systematic-debugging** when they are available. Without them: a fix starts
with a test that reproduces the bug, new behavior with a failing test, and a
refactor passes the same tests before and after.

Gate: run the relevant tests.

For prompt or skill revisions, use [prompt-evaluation.md](prompt-evaluation.md) when evaluating instruction compliance.
