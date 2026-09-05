---
name: improve-codebase-architecture
description: Scan a codebase for architectural friction and propose deepening refactors (shallow modules into deep ones). User-invoked via /skill:improve-codebase-architecture, optionally with a scope argument.
disable-model-invocation: true
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities**: refactors that turn shallow modules into deep ones. The aim is testability and navigability.

Vocabulary (use these terms exactly; don't drift into "component", "service", "boundary"):

- **Deep module**: simple interface hiding complex implementation. **Shallow**: interface nearly as complex as the implementation.
- **Deletion test**: would deleting this module concentrate complexity (good — it was doing real work), or just move it (shallow)?
- **Seam**: a boundary where behavior can vary without touching callers.

## 1. Scope, then explore

YAGNI: deepening pays off where change happens. If the user named a module or pain point, take it. Otherwise run `git log --oneline` over a good stretch of history and let the hot spots — files that keep changing — pull attention first.

Walk the scoped area and note friction:

- Understanding one concept requires bouncing between many small modules
- Modules with interfaces as complex as their implementations
- Pure functions extracted for testability while the real bugs hide in the call sites
- Untested areas, or areas hard to test through their current interface

Apply the deletion test to every suspect.

## 2. Present candidates in chat

3–5 candidates max, each as: **Files** involved · **Problem** (why the current shape causes friction) · **Solution** (plain English) · **Benefit** (what gets easier to test or change) · **Strength**: `Strong` / `Worth exploring` / `Speculative`.

End with a single **top recommendation**. Do not start refactoring. Ask which candidate to pursue, if any.

## 3. Execute one candidate at a time

For the chosen candidate: agree on the target shape in one short paragraph, then follow the **tdd skill** — write the failing test against the new (deep) interface first, keep old tests green where they describe surviving behavior, migrate callers, delete the shallow wrapper. One commit per candidate; stop after each and let the user decide whether to continue.
