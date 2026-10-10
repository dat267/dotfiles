---
name: karpathy-guidelines
description: Behavioral guardrails that reduce common LLM coding mistakes. State assumptions, write the minimum code, keep edits surgical, and verify before claiming done. Use when writing, editing, reviewing, or refactoring code, or when a task is ambiguous or multi-step. Derived from Andrej Karpathy's observations on LLM coding pitfalls.
license: MIT
---

# Karpathy Guidelines

Guardrails derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls. They trade speed for caution. Skip them for trivial work. The repo's `AGENTS.md` and existing conventions override this skill.

## 1. Think before coding

Proceed on low-risk, reversible assumptions. Ask when ambiguity changes scope, correctness, security, or irreversible effects.

- State only consequential assumptions and tradeoffs. Do not narrate routine work.
- Ask when competing interpretations require materially different changes.
- Name a simpler approach when one exists. Push back with evidence.
- Do not present an unverified assumption as fact.

## 2. Write the minimum code

Implement exactly what the task asks. Add nothing speculative.

- Write no feature beyond the request.
- Extract no abstraction for single-use code.
- Add no flexibility or configuration nobody requested.
- Handle no error that cannot occur.
- Rewrite 200 lines that fit in 50.

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

## 4. Verify before claiming done

Turn the task into a verifiable goal. Define the check before writing code.

- "Add validation" -> write failing tests for invalid inputs, then pass them.
- "Fix the bug" -> write a test that reproduces it, then pass it.
- "Refactor X" -> pass the tests before and after.

For multi-step work, plan one verification command per step. Share the plan only when coordination or approval is needed.

Follow the **tdd** skill for the failing-test loop. Follow the **systematic-debugging** skill when the cause is not obvious. Weak goals such as "make it work" force constant clarification.

Gate: run the relevant tests. Report each command, pass/fail, and the shortest decisive output, not full logs.
Do not claim success while a relevant test is red or verification is blocked.

For prompt or skill revisions, use [prompt-evaluation.md](prompt-evaluation.md) when evaluating instruction compliance.
