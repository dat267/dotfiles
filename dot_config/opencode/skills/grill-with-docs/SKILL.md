---
name: grill-with-docs
description: Use documentation to interrogate plans, code, or assumptions before acting. Read the relevant docs first, then compare them against the actual implementation or proposal to find gaps, contradictions, and missing context.
---

# Grill With Docs

Use this skill when a task touches existing code, an API, a workflow, or any system that is likely documented. Do not rely on assumptions or memory: find the docs that govern the area and use them as the source of truth for questioning the work.

## When to use

- Before implementing a feature that interacts with existing components.
- Before changing behavior that may be constrained by documented contracts or conventions.
- Before reviewing a plan, spec, or design that should align with project documentation.
- When the code and the docs disagree, or when docs are missing entirely.

## Steps

1. **Locate relevant docs**
   - Search the repo for `README*`, `docs/`, `*.md`, ADRs, architecture docs, API references, and code comments near the affected area.
   - If the project has external docs, read the local pointers to them first.

2. **Extract the contract**
   - Note what the docs say the system should do, how it should be used, and what constraints are explicit.
   - Capture exact names, paths, formats, defaults, and invariants.

3. **Grill the work**
   - If reviewing a plan/spec: does it satisfy every documented requirement? Does it contradict any documented constraint?
   - If reviewing code: does the implementation match the documented behavior? Are documented inputs/outputs handled?
   - If writing code: does the change preserve documented contracts? Will docs need updating?

4. **Report findings**
   - Quote or cite the relevant doc paths.
   - List concrete gaps, contradictions, risks, and outdated docs.
   - Recommend the smallest doc or code fix needed to restore alignment.

## Guardrails

- Docs are not automatically correct. If code and docs disagree, call out the conflict instead of silently choosing one.
- Do not invent undocumented behavior. If docs are missing, say so explicitly.
- Prefer updating docs in the same change when behavior intentionally diverges.
