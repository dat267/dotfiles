---
name: to-spec
description: Turn the current conversation into a spec file in the repo — no interview, just synthesis of what has already been discussed. User-invoked via /skill:to-spec, optionally with a slug argument.
disable-model-invocation: true
---

This skill takes the current conversation context and codebase understanding and produces a spec. Do NOT interview the user; synthesize what you already know. (To sharpen an idea before speccing it, use /skill:grill-me first.)

## Process

1. Explore the repo to ground the spec in the current state of the code, if you haven't already.

2. Sketch the **seams** at which the feature will be tested. Prefer existing seams to new ones; use the highest seam possible; if new seams are needed, propose them at the highest point. The fewer seams across the codebase, the better — the ideal is one. Confirm the seams with the user before writing.

3. Write the spec using the template below to `specs/<YYYY-MM-DD>-<slug>.md` in the repo root (create `specs/` if missing). Show the path when done. If the user asks for a GitHub issue instead and `gh` is authenticated, publish it there with `gh issue create --title ... --body-file -`.

<spec-template>

## Problem Statement

The problem the user is facing, from the user's perspective.

## Solution

The solution, from the user's perspective.

## User Stories

A numbered list, each in the form: "As an <actor>, I want a <feature>, so that <benefit>". Cover all aspects of the feature, but only ones actually discussed or implied by the conversation — do not pad.

## Implementation Decisions

Decisions already made: modules built/modified, their interfaces, technical clarifications, schema and API contracts, specific interactions.

Do NOT include file paths or code snippets — they go stale. Exception: a prototype snippet that encodes a decision more precisely than prose (state machine, schema, type shape) may be inlined, trimmed to the decision-rich parts.

## Testing Decisions

- Only external behavior at the agreed seams, never implementation details
- Which modules get tested, and at which seams
- Prior art: similar tests already in the codebase to model after

## Out of Scope

What this spec deliberately does not cover.

## Further Notes

Anything else worth carrying forward.

</spec-template>

## After the spec

Specs are inputs, not work orders. When the user is ready to implement, follow the **tdd** skill: the spec's seams define where the first failing tests go.
