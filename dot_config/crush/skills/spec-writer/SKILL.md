---
name: spec-writer
description: Turn a plan, conversation, or vague idea into a written spec. Use when the user says "write a spec", "spec this", wants a plan documented before implementation, or is about to build something and wants requirements captured first.
---

# Spec Writer

Turn a plan, conversation, or vague idea into a written Markdown spec. The spec is the single source of truth for what gets built, checked, and reviewed against. It lives in the repo (a `SPEC.md` or `docs/` file) and is written in the project's own language.

## Understand first

Before writing, gather the facts you need from the environment, not the user: read existing specs, the project README, ADRs, or domain docs so the spec uses the project's vocabulary. Only ask the user for decisions the environment can't answer.

If the idea is vague or has open branches, resolve them before writing. Work in rounds: present the open decisions with your recommendation, wait for answers, then write. Don't write a spec that silently assumes what the user hasn't decided.

## Spec structure

Follow this shape. Skip a section only when it genuinely doesn't apply, never for brevity.

```markdown
# <Feature/Thing Name>

## Goal

One or two sentences: what the user can do when this is done. State the outcome, not the mechanism.

## Non-goals

What this explicitly does NOT do. Prevents scope creep and makes "out of scope" reviewable.

## Context

The problem this solves, constraints, and related decisions. Reference existing docs instead of restating them.

## Decisions

Every decision that matters, each with the choice made and one-line rationale. If an ADR or design doc exists, link it instead of duplicating.

## Requirements

- **REQ-1**: <behavior>, verifiable by a test or acceptance check.
- **REQ-2**: ...

Numbered, imperative, testable. Each one maps to a test or an acceptance criterion.

## Acceptance criteria

```
- Given <context>, when <action>, then <observable result>.
- ...
```

Concrete and checkable. These are the "done" bar.

## Open questions

Anything not yet decided, with the decision-maker and a target date if known.
```

## Rules

- **Testable over exhaustive.** Requirements that can't be checked are opinions, not requirements. If a requirement can't be verified, rewrite it or move it to Context.
- **Decisions, not options.** The spec records what was decided and why. Present alternatives in Context or a linked ADR, not as open branches in the final spec.
- **Project language.** Use the vocabulary the project already uses. Match existing spec or doc conventions.
- **Short.** The spec should be the minimum that captures the decisions. If it reads like a design essay, cut it.
- **Facts are yours.** Look things up yourself. Never ask the user for something you can read from the repo or tools.

## Output

Write the spec to the repo (`<project-root>/SPEC.md` or follow the project's existing spec location). After writing, report where it is and the open questions that need answers before implementation.
